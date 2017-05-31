import tkinter
import tkinter.font as tk_font
from tkinter import ttk, messagebox
from bs4 import BeautifulSoup
from urllib.request import urlopen
from multiprocessing.dummy import Pool as ThreadPool
from datetime import *
from selenium.common.exceptions import TimeoutException
import urllib
import selenium.webdriver
import queue as q
import threading
import re
import time
import socket
import pickle
import os

accessed_threads = {}  # dict to keep track of last page
driver_list = []  # keep track of all available drivers
master_thread_list = []  # track all the thread links accessed
thread_list = []  # hold un accessed thread links
link_list = []  # hold the page links of the un accessed thread links
exit_check = []  # keep track of numbers of thread exited
add = 0
run = True


class WebInteractions:
    def __init__(self):
        self.driver = selenium.webdriver.PhantomJS("phantomjs.exe")
        self.driver.set_page_load_timeout(20)

    def login(self, username, password):
        while True:
            try:
                self.driver.get("https://secureforums.hardwarezone.com.sg/logon.php")
                self.driver.find_element_by_id("vb_login_username").send_keys(username)
                self.driver.find_element_by_id("vb_login_password").send_keys(password)
                self.driver.find_element_by_id("btnLogin").click()

                cookies = self.driver.get_cookies()
                cookie_check = cookies[0]

                if "secureforums" not in cookie_check['domain']:
                    print("wrong username and password")
                    cookies = None

                self.driver.quit()
                return cookies

            except TimeoutException:
                continue

    @staticmethod
    def get_page_links(url):
        global run
        while True:
            try:
                if run is False:
                    return

                page = urlopen(url, timeout=5).read()
                soup = BeautifulSoup(page, "html.parser")
                div = soup.find("span", attrs={"class": "desc"})

                if run is False:
                    return

                if url in accessed_threads:
                    last_accessed_page = accessed_threads[url][0]
                    last_max_pages = accessed_threads[url][1]

                    if div:
                        current_max_pages = int(div.text.replace("Page 1 of ", ""))
                        if current_max_pages > last_max_pages:
                            accessed_threads[url][1] = current_max_pages
                            pages_to_add = current_max_pages - last_max_pages
                            link_list.append(url)
                            for num in range(2, pages_to_add + 1):
                                replacer = ("-" + str(num) + ".html")
                                link = url.replace(".html", replacer)
                                link_list.append(link)

                        if current_max_pages > last_accessed_page:
                            for num in range(last_accessed_page, current_max_pages + 1):
                                if run is False:
                                    return
                                replacer = ("-" + str(num) + ".html")
                                link = url.replace(".html", replacer)
                                link_list.append(link)
                else:
                    link_list.append(url)

                    if div:  # multiple pages
                        max_pages = int(div.text.replace("Page 1 of ", "")) + 1
                        accessed_threads[url] = [0, max_pages - 1]
                        for num in range(2, max_pages):
                            if run is False:
                                return
                            replacer = ("-" + str(num) + ".html")
                            link = url.replace(".html", replacer)
                            link_list.append(link)
                    else:
                        accessed_threads[url] = [0, 1]
                break

            except urllib.request.URLError:
                print(urllib.request.URLError)
                continue
            except socket.timeout:
                print(socket.timeout)
                continue

    @staticmethod
    def get_thread_links(url):
        global run
        if run is False:
            return

        page = urlopen(url).read()
        soup = BeautifulSoup(page, "html.parser")

        if run is False:
            return

        threads = soup.findAll("a", attrs={"id": re.compile("thread_title_(\d+)")})
        for anchors in threads:
            if run is False:
                return

            thread_link = "http://forums.hardwarezone.com.sg" + anchors.get("href")
            if thread_link not in master_thread_list:
                master_thread_list.append(thread_link)  # get ever larger
                thread_list.append(thread_link)  # kept small


class MultiThreading(threading.Thread):
    def __init__(self, queue, driver):
        threading.Thread.__init__(self)
        self.queue = queue
        self.driver = driver

    def run(self):
        global run
        while run:
            try:
                global add
                if not run:
                    break

                link = self.queue.get()

                if not run:
                    break

                self.driver.get(link)
                soup = BeautifulSoup(self.driver.page_source, "html.parser")

                if not run:
                    break

                temp = soup.findAll("a", attrs={"class": "vbseo_like_link"})
                length = len(soup.findAll("img", attrs={"class": "hwz-like-button", "title": "Like"}))
                if length > 0:
                    like_buttons = self.driver.find_elements_by_class_name("vbseo_like_link")
                    for button, like in zip(like_buttons, temp):
                        if not run:
                            break
                        if like.find("img").get("title") == "Like":
                            #button.click()
                            continue
                    time.sleep(2)
                    add += length

                if not run:
                    break

                print(self.driver.title, ":", self.driver)

                start = link.rindex("-")
                stop = link.rindex(".")
                pages = int(link[start + 1:stop])
                if pages > 1000:
                    pages = 1
                    main_url = link
                else:
                    main_url = link[:start] + ".html"
                if pages > accessed_threads[main_url][0]:
                    accessed_threads[main_url][0] = pages

                print(accessed_threads[main_url])

                if not run:
                    break
                self.queue.task_done()

            except TimeoutException:
                print("Timeout")
                continue

        if not run:
            self.queue.task_done()
            exit_check.append(True)
        print("Exited thread")


class MainApp(tkinter.Tk):
    def __init__(self):
        tkinter.Tk.__init__(self)

        self.resizable(width=False, height=False)
        self.minsize(height=300, width=300)
        self.maxsize(height=300, width=300)
        self.protocol("WM_DELETE_WINDOW", self.window_close)
        self.title("HWZ Bot")

        container = tkinter.Frame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=0)
        container.grid_rowconfigure(1, weight=1)
        container.grid_rowconfigure(2, weight=1)
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)
        container.grid_columnconfigure(2, weight=1)

        self.frames = {}
        for F in (LoginPage, StatusPage):
            page_name = F.__name__
            frame = F(parent=container, controller=self)
            self.frames[page_name] = frame

            frame.grid(row=1, column=1)
        self.show_frame("LoginPage")

    def show_frame(self, page_name):
        frame = self.frames[page_name]
        frame.tkraise()

    def get_frame(self, page_name):
        return self.frames[page_name]

    def window_close(self):
        global run

        page = self.get_frame("StatusPage")
        if page.stopButton["state"] == "disabled":
            messagebox.askokcancel("Please wait...", "The application cannot be stopped when it is initializing. \n"
                                                     "Please wait a while before trying again.")

        else:
            try:
                print("No error")
                page = self.get_frame("LoginPage")
                if page.stopped:
                    terminate_drivers()
                    self.destroy()
                    self.quit()

                else:  # stop button was not clicked before exiting
                    run = False
                    page.current_tread.do_run = False

                    page = self.get_frame("StatusPage")
                    if page.statusLabel["text"] == "Status: Giving likes...":
                        while not page.queue.empty():
                            # print("Clearing queue")
                            page.queue.get()
                            page.queue.task_done()

                        while exit_check.count(True) != 4:
                            if exit_check.count(True) == 0:
                                page.gui_update("statusLabel", "Waiting for threads to stop")
                            elif exit_check.count(True) == 1:
                                page.gui_update("statusLabel", "Waiting for thread 2 to stop")
                            elif exit_check.count(True) == 2:
                                page.gui_update("statusLabel", "Waiting for thread 3 to stop")
                            elif exit_check.count(True) == 3:
                                page.gui_update("statusLabel", "Waiting for thread 4 to stop")
                            self.update()

                        page.gui_update("statusLabel", "All threads exited.")
                        print("All threads exited")

                    terminate_drivers()
                    self.destroy()
                    self.quit()

            except:
                print("Error")
                terminate_drivers()
                self.destroy()
                self.quit()


class LoginPage(tkinter.Frame):
    def __init__(self, parent, controller):
        frame = tkinter.Frame
        frame.__init__(self, parent)
        frame.configure(self, borderwidth=50)

        self.frame = frame
        self.controller = controller
        self.parent = parent
        self.username = tkinter.StringVar()
        self.password = tkinter.StringVar()
        self.saved_cookie = None
        self.current_tread = None
        self.start_url = None
        self.queue = None
        self.stopped = False
        self.count = 1

        if os.path.exists("session.pkl"):
            global accessed_threads
            accessed_threads = pickle.load(open("session.pkl", "rb"))

        main_font = tk_font.Font(family="Arial", size=10)
        other_font = tk_font.Font(family="Arial", size=8)
        self.bind("<Return>", lambda enter: self.login())

        # username
        self.username_label = ttk.Label(self, text="USERNAME", font=main_font)
        self.username_label.pack()
        self.usernameEntry = ttk.Entry(self, width=30, textvariable=self.username, justify=tkinter.CENTER)
        self.usernameEntry.bind("<Return>", lambda enter: self.login())
        self.usernameEntry.pack()

        # password
        self.password_label = ttk.Label(self, text="PASSWORD", font=main_font)
        self.password_label.pack(pady=(10, 0))
        self.passwordEntry = ttk.Entry(self, width=30, show="\u2022", textvariable=self.password, justify=tkinter.CENTER)
        self.passwordEntry.bind("<Return>", lambda enter: self.login())
        self.passwordEntry.pack()

        # submit
        self.loginButton = tkinter.Button(self, text="START", width=22, height=2,
                                          command=lambda: self.login(),  font=main_font)
        self.loginButton.bind("<Return>", lambda enter: self.login())
        self.loginButton.pack(pady=(5, 0))

        # creator
        ttk.Label(parent, text="Creator: GYT, 2017", font=other_font).place(x=195, y=280)

    def threaded_gui(self):
        global run
        run = True
        page = self.controller.get_frame("StatusPage")
        page.gui_update("userLabel", self.username)
        page.run_timer()
        page.gui_update("statusLabel", "Setting up drivers...")
        page.stopButton.configure(state=tkinter.DISABLED)

        self.queue = q.Queue()
        self.current_tread = threading.current_thread()
        self.current_tread.do_run = True

        for i in range(4):  # start four threads first, waiting for queue
            print("Starting thread", i+1)

            driver = selenium.webdriver.PhantomJS("phantomjs.exe")
            driver.set_page_load_timeout(65)
            driver_list.append(driver)

            for item in self.saved_cookie:
                driver.add_cookie({
                    'domain': '.hardwarezone.com.sg',
                    'name': item["name"],
                    'value': item["value"],
                    'path': '/',
                    'expires': None
                })

            thread = MultiThreading(self.queue, driver)
            thread.setDaemon(True)
            thread.start()

        page.gui_update("statusLabel", "Starting workload...")
        page.stopButton.configure(state=tkinter.NORMAL)
        page.update_likes()
        page.run_likes_per_hour()

        while self.current_tread.do_run:
            self.stopped = False
            page.gui_update("statusLabel", "Scrapping thread page...")

            if self.count > 1:
                self.start_url = ("http://forums.hardwarezone.com.sg/eat-drink-man-woman-16/index" + str(self.count) + ".html")
            else:
                self.start_url = "http://forums.hardwarezone.com.sg/eat-drink-man-woman-16/"

            WebInteractions.get_thread_links(self.start_url)

            if self.current_tread.do_run is False:
                break

            page.gui_update("statusLabel", "Scrapping page links...")
            pool = ThreadPool(4)
            pool.map(WebInteractions.get_page_links, thread_list)  # uses global run to check for stops
            pool.close()
            pool.join()

            if self.current_tread.do_run is False:
                break

            page.gui_update("statusLabel", "Giving likes...")  # error here, cant be stopped
            for link in link_list:
                if self.current_tread.do_run:
                    self.queue.put(link)
                else:
                    break
            print("Done putting queue")

            if self.current_tread.do_run is False:
                break
            print("Waiting for queue to finish")
            self.queue.join()
            print("Queue finished!")

            if self.current_tread.do_run is False:
                break

            del thread_list[:]
            del link_list[:]
            self.count += 1

        print("Quitting thread")
        self.stopped = True
        terminate_drivers()

    def login(self):
        self.usernameEntry.configure(state=tkinter.DISABLED)
        self.passwordEntry.configure(state=tkinter.DISABLED)
        self.loginButton.configure(text="Attempting to login...", state=tkinter.DISABLED)
        self.update()

        self.username = self.usernameEntry.get()
        self.password = self.passwordEntry.get()

        if len(self.username) < 6 or len(self.password) == 0:
            self.message_box(0)
            self.usernameEntry.focus()
        else:
            instance = WebInteractions()  # initialize
            self.saved_cookie = instance.login(self.username, self.password)  # store returned cookie

            if not self.saved_cookie:  # if wrong username or password
                self.message_box(0)
                self.usernameEntry.focus()
            else:  # correct username and password
                self.message_box(1)
                self.controller.show_frame("StatusPage")

                threading.Thread(target=self.threaded_gui).start()

    def message_box(self, type_login):
        if type_login == 0:
            if messagebox.askretrycancel("Error", "The username and/or password are invalid!"):  # retry
                self.usernameEntry.configure(state=tkinter.NORMAL)
                self.passwordEntry.configure(state=tkinter.NORMAL)
                self.loginButton.configure(text="START", state=tkinter.NORMAL)
            else:  # cancel
                app.destroy()
        else:
            messagebox.showinfo("Login attempt", "You have logged in successfully!")


class StatusPage(ttk.Frame):
    def __init__(self, parent, controller):
        frame = ttk.Frame
        frame.__init__(self, parent)
        frame.configure(self, relief=tkinter.SOLID, borderwidth=43)

        self.controller = controller
        self.seconds = 0
        self.likes = 0
        self.run_timer_identifier = 0
        self.run_like_identifier = 0
        self.update_likes_identifier = 0

        main_font = tk_font.Font(family="Arial", size=10)

        self.userLabel = ttk.Label(self, font=main_font)
        self.userLabel.place(x=-40, y=-40)
        self.timeLabel = ttk.Label(self, font=main_font)
        self.timeLabel.pack()
        self.likesLabel = ttk.Label(self, text="Likes given: 0", font=main_font)
        self.likesLabel.pack()
        self.perHourLabel = ttk.Label(self, text="Likes/hour: ", font=main_font)
        self.perHourLabel.pack()
        self.statusLabel = ttk.Label(self, text="Current status: ", font=main_font)
        self.statusLabel.pack()

        self.stopButton = tkinter.Button(self, text="STOP", width=22, height=2,
                                         command=lambda: self.logout_hwz(self.controller), font=main_font)
        self.stopButton.pack(pady=(5, 0))

    def logout_hwz(self, controller):
        global run

        pickle.dump(accessed_threads, open("session.pkl", "wb"))

        self.stopButton.configure(text="Stopping processes", state=tkinter.DISABLED)
        self.timeLabel.after_cancel(self.run_timer_identifier)
        self.perHourLabel.after_cancel(self.run_like_identifier)
        self.likesLabel.after_cancel(self.update_likes_identifier)
        self.update()

        page = self.controller.get_frame("LoginPage")
        page.current_tread.do_run = False
        run = False

        time.sleep(3)

        if self.statusLabel["text"] == "Status: Giving likes...":
            while not page.queue.empty():
                # print("Clearing queue")
                page.queue.get()
                page.queue.task_done()
            print("Done clearing queue")

            while exit_check.count(True) != 4:
                if exit_check.count(True) == 0:
                    self.gui_update("statusLabel", "Waiting for threads to stop")
                elif exit_check.count(True) == 1:
                    self.gui_update("statusLabel", "Waiting for thread 2 to stop")
                elif exit_check.count(True) == 2:
                    self.gui_update("statusLabel", "Waiting for thread 3 to stop")
                elif exit_check.count(True) == 3:
                    self.gui_update("statusLabel", "Waiting for thread 4 to stop")
                self.update()
            print("All threads exited")
            self.gui_update("statusLabel", "All threads exited.")

        messagebox.showinfo("Stop event", "The processes are stopped successfully!")

        page = self.controller.get_frame("LoginPage")
        page.usernameEntry.configure(state=tkinter.NORMAL)
        page.passwordEntry.configure(state=tkinter.NORMAL)
        page.loginButton.configure(text="START", state=tkinter.NORMAL)

        controller.show_frame("LoginPage")

        self.seconds = 0
        self.likes = 0
        self.run_timer_identifier = 0
        self.run_like_identifier = 0
        self.update_likes_identifier = 0
        self.stopButton.configure(text="STOP", state=tkinter.NORMAL)
        self.gui_update("statusLabel", "")
        del exit_check[:]

    def gui_update(self, widget, value=None):
        if widget == "userLabel":
            self.userLabel.configure(text="You are logged in as: " + value)
        elif widget == "statusLabel":
            self.statusLabel.configure(text="Status: " + str(value))

    def run_timer(self):
        self.seconds += 1
        timer = format_time(self.seconds)
        self.timeLabel.configure(text="Time elapsed: " + timer)
        self.run_timer_identifier = self.timeLabel.after(1000, self.run_timer)

    def run_likes_per_hour(self):
        likes_per_hour = (3600 / int(self.seconds)) * int(self.likes)
        likes_per_hour = format(int(round(likes_per_hour)), ",d")
        self.perHourLabel.configure(text="Likes/hour: " + str(likes_per_hour))
        self.run_like_identifier = self.perHourLabel.after(5000, self.run_likes_per_hour)

    def update_likes(self):
        global add
        self.likes = int(self.likes + add)
        self.likesLabel.configure(text="Likes given: " + str(self.likes))
        add = 0
        self.update_likes_identifier = self.likesLabel.after(3000, self.update_likes)


def format_time(seconds):
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return '{:02d}:{:02d}:{:02d}'.format(hours, minutes, seconds)


def terminate_drivers():
    if driver_list:
        print("Stopping drivers")
        for driver in driver_list:
            driver.quit()
        del driver_list[:]
    else:
        print("No drivers to stop")

if __name__ == '__main__':
    app = MainApp()
    app.mainloop()
