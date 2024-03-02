# imports
import os
import base64
import markdown
from io import BytesIO
import string
import requests
import random
from requests_html import HTMLSession
from dotenv import load_dotenv
from supabase import create_client
from supabase.client import Client, ClientOptions
from flask import Flask, render_template, request, redirect, session, g, url_for
import asyncio
from pyppeteer import launch
import textwrap
from PIL import Image
from google.generativeai import configure, GenerativeModel
from gotrue import SyncSupportedStorage
from werkzeug.local import LocalProxy
from playwright.sync_api import sync_playwright

# load env
load_dotenv()

# init Supabase
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY_SEC")
supabase = create_client(url, key)

# init gemini pro vision
GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
configure(api_key=GOOGLE_API_KEY)
model = GenerativeModel("gemini-pro-vision")

# flask init
app = Flask(__name__)

# flask session
app.secret_key = "super secret key"
app.config["SESSION_TYPE"] = "filesystem"


# helper functions
def launch_browser(web_url):
    # async def screenshot():
    #     browser = await launch(
    #         handleSIGINT=False, handleSIGTERM=False, handleSIGHUP=False
    #     )
    #     page = await browser.newPage()
    #     await page.goto(web_url)
    #     await page.screenshot({"path": "screenshot.png", "fullPage": True})
    #     await browser.close()

        

        with sync_playwright() as p:
            browser = p.chromium.launch(headless = False,handle_sigint=False, handle_sigterm=False, handle_sighup=False, timeout=0)

            page = browser.new_page()
            page.goto(web_url)

            # Save the screenshot
            page.screenshot(path="screenshot.png", full_page=True)

    # loop = asyncio.new_event_loop()
    # asyncio.set_event_loop(loop)
    # asyncio.get_event_loop().run_until_complete(screenshot())


def compress_image(image):
    width, height = image.size
    new_size = (width // 2, height // 2)
    resized_image = image.resize(new_size)
    return resized_image


def img_process():
    N = 7
    res = "".join(random.choices(string.ascii_lowercase + string.digits, k=N))
    rand = str(res)
    supabase.storage.from_("images").upload(
        file="screenshot.png",
        path=f"screenshot/screenshot_{rand}.png",
        file_options={"content-type": "image/png", "x-upsert": "True"},
    )
    url_img1 = supabase.storage.from_("images").get_public_url(
        f"screenshot/screenshot_{rand}.png"
    )
    response = requests.get(url_img1)
    img_data = BytesIO(response.content)
    img = Image.open(img_data)
    com_img = compress_image(img)
    return com_img


def preview_img(img):
    width, height = img.size
    if width > height:
        height = height // 2
    else:
        height = height // 7
    left = 0
    upper = 0
    right = left + width
    lower = upper + height
    # left, upper, right, lower
    box = (left, upper, right, lower)
    img2_data = img.crop(box)
    img2_data = img2_data.convert("RGB")
    img2_bytes_io = BytesIO()
    img2_data.save(img2_bytes_io, format="PNG")  # Adjust the format as needed
    img2_bytes = img2_bytes_io.getvalue()
    return img2_bytes

# function to get tags from desc
def get_key(desc):
    pass

# routes
@app.route("/")
def home_page():
    return render_template("index.html")


@app.route("/get-started")
def form():
    return render_template("form.html")


@app.route("/login", methods=["POST", "GET"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        supabase.auth.sign_in(email=email, password=password)
        user = supabase.auth.get_user()
        session["user_id"] = user["id"]
        return redirect("/get-started")
    else:
        return render_template("login.html")


@app.route("/process_form", methods=["POST","GET"])
def process_form():
    name = request.form.get("name")
    web_url = request.form.get("web_url")
    description = request.form.get("desc")
    tech_stack = request.form.get("tech_stack")
    sys_prompt = request.form.get("prompt")
    more_info = request.form.get("more")
    check = request.form.getlist("checkbox-2")
    # web_url = str(web_url)  
    launch_browser(web_url)
    session["name"] = name
    session["description"] = description
    session["web_url"] = web_url
    session["tech_stack"] = tech_stack
    session["sys_prompt"] = sys_prompt
    session["more_info"] = more_info
    session["check"] = check
    return redirect("/suggest")


@app.route("/suggest")
def try_page():
    name = session.get("name")
    description = session.get("description")
    tech_stack = session.get("tech_stack")
    sys_prompt = session.get("sys_prompt")
    more_info = session.get("more_info")
    check = session.get("check")
    image = img_process()
    rgb_img = image.convert("RGB")
    prompt = f"You are a website developer tasked with evaluating the {name} app. The current tech stack used to build this website is {tech_stack} and {check}. Begin by thoroughly understanding the features and functionality of the app and allign your understanding with {description} and{more_info} it responsive.{sys_prompt}. Once you have a comprehensive understanding, analyze the website for potential areas of improvement. If you identify any, provide detailed technical suggestions. Your response should include steps taken to understand the existing app, specific areas for improvement. Be sure to consider the given tech stack while proposing technical improvements."
    response = model.generate_content([prompt, rgb_img])
    desc = response.text
    mark = markdown.markdown(desc)
    prev_img = preview_img(image)
    encoded_img = base64.b64encode(prev_img).decode("utf-8")
    
    return render_template(
        "suggestion.html",
        prev_img=encoded_img,
        name=session.get("name"),
        description=session.get("description"),
        desc=mark,
    )



@app.route("/getter_url")
def getter_url():
    url = session.get("web_url")
    return redirect(url)

# if __name__ == "__main__":
#     app.run(debug=True)