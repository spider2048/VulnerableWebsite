from flask import Flask, render_template, make_response, url_for, request, redirect, flash, send_from_directory
import secrets
import time
import json
from markupsafe import escape
import logging

app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.disabled = True

# Error handling ######################################################################################################
class AppError(Exception):
    def __init__(self, cause):
        self.cause = cause
        super().__init__(self)

    def __str__(self):
        return "Error Occurred -> %s" % self.cause


# Variables ###########################################################################################################
class App:
    credentials = {}

    with open("details.txt", "r") as f:
        temp = f.read().split("\n")
        print(temp)
        last_postId = int(temp[0])
        last_userId = int(temp[1])
        f.close()
        del temp

    file = None
    posts_file = open("posts.json", "r")
    posts = json.load(posts_file)
    posts_file.close()


# Functions ###########################################################################################################
def add_creds(username, password):
    username = username.replace("/", "")
    password = password.replace("/", "")
    for cred in App.credentials:
        if App.credentials[cred]["username"] == username:
            return False
    App.file = open("credentials.json", "w+")
    App.last_userId += 1

    with open("details.txt", "w") as f:
        f.write(str(App.last_userId) + "\n" + str(App.last_postId))
        f.close()

    key = secrets.token_hex(16)
    App.credentials[str(App.last_userId)] = dict(username=username, password=password, key=key, time=time.time())
    json.dump(App.credentials, App.file, indent=4)
    App.file.close()
    return key


def modify_creds(userId, key):
    if userId in App.credentials:
        App.file = open("credentials.json", "w+")
        App.credentials[userId]["key"] = key
        App.credentials[userId]["time"] = time.time()
        json.dump(App.credentials, App.file, indent=4)
        App.file.close()
    else:
        raise AppError("No userId [%s] to modify" % userId)


def add_post(userId, post_title, post_body):
    if not (post_title and post_body):
        return False
    App.last_postId += 1

    with open("details.txt", "w") as f:
        f.write(str(App.last_userId) + "\n" + str(App.last_postId))
        f.close()
    print(f"POST: {App.credentials[userId]['username']}")
    if userId in App.credentials:
        try:
            App.posts[userId]
        except KeyError:
            App.posts[userId] = {}
        App.posts[userId][App.last_postId] = {}
        App.posts[userId][App.last_postId]["title"] = post_title
        App.posts[userId][App.last_postId]["body"] = post_body  # TODO: Add Dm or controls
        App.posts_file = open("posts.json", "w")
        json.dump(App.posts, App.posts_file, indent=4)
        App.posts_file.close()
        return True
    else:
        return False

@app.route("/getContent")
def get_content():
    content = ""
    for userid in App.posts:
        for postId in App.posts[userid]:
            content += "<p> <em>%s</em> <b>%s</b>: " \
                        "%s</p>" % (App.credentials[userid]["username"], App.posts[userid][postId]["title"],
                            App.posts[userid][postId]["body"])
    return content

def build_home_page(userId):
    content = get_content()
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en" xmlns="http://www.w3.org/1999/html">
    <head>
        <meta charset="UTF-8">
        <title>Vuln Chat server | Welcome {App.credentials[userId]["username"]}</title>
        
        <style>
            .post {{
                width: auto;height: auto;margin: auto;
                padding: 2px 0px 0px 0px;
                border: 3px solid;
            }}
        </style>

        <script>
            const interval = setInterval(function() {{
                var xmlhttp = new XMLHttpRequest();
                xmlhttp.open("GET", "/getContent", true); xmlhttp.send();
                xmlhttp.onload = () => document.getElementById("PostContainer").innerHTML = xmlhttp.responseText;
            }}, 1000);
        </script>
    </head>
    <body>
        
        <div align="right" style="font-size:20px">
            <a href="/logout">Logout?</a>
        </div>
        <div align="center" style="font-size:20px">
            <h3> Welcome: {App.credentials[userId]["username"]} </h3>
			
			<div class=post id=PostContainer>
				{content}
            </div>
            
			<b>New post</b>
            <form action="/{userId}/post" method="post"">
                <label for="title">Title:</label>
                <input type="text" name="title" id="title" maxlength="10"> <br>
                <label for="body">Body:</label>
                <textarea name="body" id="body" cols="40" rows="5" maxlength="200"></textarea> <br>
                <em>Post is public!</em>
                <input type="submit">
            </form>
        </div>
    </body>
    </html>
    """
    return html_content


# Startup #############################################################################################################
try:
    App.file = open("credentials.json", "r")
    App.credentials = json.load(App.file)
except FileNotFoundError:
    raise AppError("File `credentials.json` not found")
except json.decoder.JSONDecodeError:
    raise AppError("JSON DECODE ERROR")


# Website routing #####################################################################################################
@app.route("/")
def get_login_page():
    return render_template("login.html")


@app.route("/login", methods=["POST", "GET"])
def process_login():
    if request.method == "POST":
        username = request.form["username"].lower()
        password = request.form["password"]
        if username and password:
            for cred in App.credentials:
                if App.credentials[cred]["username"] == username and App.credentials[cred]["password"] == password:
                    if App.credentials[cred]["time"] - time.time() > 600000 or request.cookies.get("key") != App.credentials[cred]["key"]:
                        print(f"LOGIN: {username}")

                        s = secrets.token_hex(16)
                        modify_creds(cred, s)
                        resp = make_response(redirect(url_for("get_home_page", userId=cred)))
                        resp.set_cookie("key", s)
                        return resp
                    else:
                        return redirect(url_for("get_home_page", userId=cred))
        return render_template("loginError.html", status="INVALID CREDENTIALS")
    else:
        return render_template("loginError.html", status="INVALID REQUEST METHOD: %s" % request.method)


@app.route("/<userId>/home")
def get_home_page(userId):
    if userId in App.credentials:
        if App.credentials[userId]["key"] == request.cookies.get("key") and App.credentials[userId]["time"] - time.time() <= 600000:
            return build_home_page(userId)
        else:
            return render_template("loginError.html", status="Invalid Cookie: %s" % request.cookies.get("key"))
    else:
        return render_template("loginError.html", status="Invalid userId: %s" % escape(userId))


@app.route("/registerPage")
def get_register_page():
    return render_template("register.html")


@app.route("/register", methods=['GET', 'POST'])
def register_user():
    if request.method == "POST":
        username = request.form["username"].lower()
        password = request.form["password"]
        if username and password:
            key = add_creds(username, password)
            if key:
                print(f"REGISTER: {username}")
                resp = make_response(redirect(url_for("get_home_page", userId=str(App.last_userId))))
                resp.set_cookie("key", key)
                return resp
            else:
                return render_template("loginError.html", status="USER: %s ALREADY IN DATABASE" % username)
        else:
            return render_template("registerError.html", status="INVALID CREDENTIALS")
    else:
        return render_template("registerError.html", status="INVALID METHOD: %s" % request.method)


@app.route("/logout")
def logout():
    resp = make_response(redirect(url_for("get_login_page")))
    resp.set_cookie("key", "")
    return resp


@app.route("/<userId>/post", methods=["POST", "GET"])
def post_content(userId):
    if request.method == "POST":
        if request.cookies.get("key") == App.credentials[userId]["key"]:
            title = escape(request.form["title"])
            body = escape(request.form["body"])
            if title and body:
                add_post(userId, title, body)

    return redirect(url_for("get_home_page", userId=userId))  # TODO: Add an error message for all

app.run(host="localhost", port=1338)
