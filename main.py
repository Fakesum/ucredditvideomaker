#!/usr/bin/env python
from subprocess import Popen
from os import name

from prawcore import ResponseException

from reddit.subreddit import get_subreddit_threads
from utils.cleanup import cleanup
from utils.console import print_markdown, print_step, print_substep
from utils.polllib import wrap_poll, wrap_filter
from utils import settings
import translators as ts

from video_creation.background import (
    get_background_config,
)
from video_creation.final_video import FinalVideo
import undetected_chromedriver as uc
from video_creation.voices import save_text_to_mp3

__VERSION__ = "2.3.1"
__BRANCH__ = "develop"

print(
    """
██████╗ ███████╗██████╗ ██████╗ ██╗████████╗    ██╗   ██╗██╗██████╗ ███████╗ ██████╗     ███╗   ███╗ █████╗ ██╗  ██╗███████╗██████╗
██╔══██╗██╔════╝██╔══██╗██╔══██╗██║╚══██╔══╝    ██║   ██║██║██╔══██╗██╔════╝██╔═══██╗    ████╗ ████║██╔══██╗██║ ██╔╝██╔════╝██╔══██╗
██████╔╝█████╗  ██║  ██║██║  ██║██║   ██║       ██║   ██║██║██║  ██║█████╗  ██║   ██║    ██╔████╔██║███████║█████╔╝ █████╗  ██████╔╝
██╔══██╗██╔══╝  ██║  ██║██║  ██║██║   ██║       ╚██╗ ██╔╝██║██║  ██║██╔══╝  ██║   ██║    ██║╚██╔╝██║██╔══██║██╔═██╗ ██╔══╝  ██╔══██╗
██║  ██║███████╗██████╔╝██████╔╝██║   ██║        ╚████╔╝ ██║██████╔╝███████╗╚██████╔╝    ██║ ╚═╝ ██║██║  ██║██║  ██╗███████╗██║  ██║
╚═╝  ╚═╝╚══════╝╚═════╝ ╚═════╝ ╚═╝   ╚═╝         ╚═══╝  ╚═╝╚═════╝ ╚══════╝ ╚═════╝     ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
"""
)
# Modified by JasonLovesDoggo
print_markdown(
    "### Thanks for using this tool! [Feel free to contribute to this project on GitHub!](https://lewismenelaws.com) If you have any questions, feel free to reach out to me on Twitter or submit a GitHub issue. You can find solutions to many common problems in the [Documentation](https://luka-hietala.gitbook.io/documentation-for-the-reddit-bot/)"
)
print_step(f"You are using v{__VERSION__} of the bot")

def minimal_poll(func):
    while True:
        try:
            func()
            return True
        except Exception as e:
            print(e)

driver: uc.Chrome = None
from selenium.webdriver.common.by import By
import time

def download_screenshots(driver: uc.Chrome, reddit_object, comments_created):
    from pathlib import Path

    def reset():
        list(filter((lambda tab: (lambda b: driver.close())(driver.switch_to.window(tab))), driver.window_handles[1:]))
        driver.switch_to.window(driver.window_handles[0])

    @wrap_filter
    @wrap_poll(None, return_val=True, on_failer=reset)
    def comment_screenshot(idx, reddit_object):

        driver.switch_to.new_window()
        driver.get(f"""https://reddit.com{reddit_object["comments"][idx]["comment_url"]}""")

        driver.execute_script("arguments[0].scrollIntoView();",driver.find_element(By.XPATH, f"""//div[@id='t1_{reddit_object["comments"][idx]['comment_id']}']"""))
        driver.execute_script("window.scrollBy(0,-300);")
        time.sleep(1)
        driver.find_element(By.XPATH, f"""//div[@id='t1_{reddit_object["comments"][idx]['comment_id']}']""").screenshot(f"assets/temp/png/comment_{idx}.png")

        driver.close()
        driver.switch_to.window(driver.window_handles[0])


    print_step("Downloading screenshots of reddit posts...")
    
    # ! Make sure the reddit screenshots folder exists
    Path("assets/temp/png").mkdir(parents=True, exist_ok=True)

    driver.get(reddit_object["thread_url"])

    print_substep("Skipping translation...")

    comment_screenshot(comments_created, common=reddit_object)
    
    driver.find_element(By.XPATH, f"//div[@data-testid='post-container']").screenshot("assets/temp/png/title.png")
    print_substep("Comments downloaded Successfully.", style="bold greEen")
    
    driver.quit()

def main(POST_ID=None):
    cleanup()
    reddit_object = get_subreddit_threads(POST_ID)
    comments_created = save_text_to_mp3(reddit_object)
    
    print_substep("Launching Headless Browser...")

    options = uc.ChromeOptions()
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-dev-shm-usage")
    options.timeouts = 10000
    
    driver = uc.Chrome(options=options, version_main=106, no_sandbox=False, headless=True) #TODO: Make Headless
    
    download_screenshots(driver, reddit_object, comments_created)

    bg_config = get_background_config()
    FinalVideo().make(comments_created, reddit_object, bg_config)


def run_many(times):
    for x in range(1, times + 1):
        print_step(
            f'on the {x}{("th", "st", "nd", "rd", "th", "th", "th", "th", "th", "th")[x % 10]} iteration of {times}'
        )  # correct 1st 2nd 3rd 4th 5th....
        main()
        Popen("cls" if name == "nt" else "clear", shell=True).wait()


def shutdown():
    print_markdown("## Clearing temp files")
    cleanup()
    print("Exiting...")
    exit()


if __name__ == "__main__":
    config = settings.check_toml("utils/.config.template.toml", "config.toml")
    config is False and exit()
    try:
        if config["settings"]["times_to_run"]:
            run_many(config["settings"]["times_to_run"])

        elif len(config["reddit"]["thread"]["post_id"].split("+")) > 1:
            for index, post_id in enumerate(config["reddit"]["thread"]["post_id"].split("+")):
                index += 1
                print_step(
                    f'on the {index}{("st" if index % 10 == 1 else ("nd" if index % 10 == 2 else ("rd" if index % 10 == 3 else "th")))} post of {len(config["reddit"]["thread"]["post_id"].split("+"))}'
                )
                main(post_id)
                Popen("cls" if name == "nt" else "clear", shell=True).wait()
        else:
            main()
    except KeyboardInterrupt:  # TODO won't work with async code
        shutdown()
    except ResponseException:
        # error for invalid credentials
        print_markdown("## Invalid credentials")
        print_markdown("Please check your credentials in the config.toml file")

        shutdown()

        # todo error
