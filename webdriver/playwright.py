from asyncio import as_completed
from pathlib import Path
from typing import Dict, Optional

import translators as ts
from attr import attrs, attrib
from attr.validators import instance_of
from playwright.async_api import Browser, Playwright, Page, BrowserContext, ElementHandle
from playwright.async_api import async_playwright, TimeoutError
from rich.progress import track

from utils import settings
from utils.console import print_step, print_substep

import webdriver.common as common

common.default_exception = TimeoutError


@attrs
class Browser:
    """
    Args:
        default_Viewport (dict):Pyppeteer Browser default_Viewport options
        browser (BrowserCls): Pyppeteer Browser instance
    """
    default_Viewport: dict = attrib(
        validator=instance_of(dict),
        default={
            # 9x21 to see long posts
            "width": 500,
            "height": 1200,
        },
        kw_only=True,
    )
    playwright: Playwright
    browser: Browser
    context: BrowserContext

    def get_browser(
            self,
    ) -> None:
        """
        Creates Playwright instance & browser
        """
        self.playwright = async_playwright().start()
        self.browser = self.playwright.chromium.launch()
        self.context = self.browser.new_context(viewport=self.default_Viewport)

    def close_browser(
            self,
    ) -> None:
        """
        Closes Playwright stuff
        """
        self.context.close()
        self.browser.close()
        self.playwright.stop()


class Flaky:
    """
    All methods decorated with function catching default exceptions and writing logs
    """

    @staticmethod
    @common.catch_exception
    def find_element(
            selector: str,
            page_instance: Page,
            options: Optional[dict] = None,
    ) -> ElementHandle:
        return (
            page_instance.wait_for_selector(selector, **options)
            if options
            else page_instance.wait_for_selector(selector)
        )

    @common.catch_exception
    def click(
            self,
            page_instance: Optional[Page] = None,
            query: Optional[str] = None,
            options: Optional[dict] = None,
            *,
            find_options: Optional[dict] = None,
            element: Optional[ElementHandle] = None,
    ) -> None:
        if element:
            element.click(**options) if options else element.click()
        else:
            results = (
                self.find_element(query, page_instance, **find_options)
                if find_options
                else self.find_element(query, page_instance)
            )
            results.click(**options) if options else results.click()

    @common.catch_exception
    def screenshot(
            self,
            page_instance: Optional[Page] = None,
            query: Optional[str] = None,
            options: Optional[dict] = None,
            *,
            find_options: Optional[dict] = None,
            element: Optional[ElementHandle] = None,
    ) -> None:
        if element:
            element.screenshot(**options) if options else element.screenshot()
        else:
            results = (
                self.find_element(query, page_instance, **find_options)
                if find_options
                else self.find_element(query, page_instance)
            )
            results.screenshot(**options) if options else results.screenshot()


@attrs(auto_attribs=True)
class RedditScreenshot(Flaky, Browser):
    """
    Args:
        reddit_object (Dict): Reddit object received from reddit/subreddit.py
        screenshot_idx (int): List with indexes of voiced comments
        story_mode (bool): If submission is a story takes screenshot of the story
    """
    reddit_object: dict
    screenshot_idx: list
    story_mode: Optional[bool] = attrib(
        validator=instance_of(bool),
        default=False,
        kw_only=True
    )

    def __attrs_post_init__(
            self
    ):
        self.post_lang: Optional[bool] = settings.config["reddit"]["thread"]["post_lang"]

    def __dark_theme(  # TODO isn't working
            self,
            page_instance: Page,
    ) -> None:
        """
        Enables dark theme in Reddit

        Args:
            page_instance: Pyppeteer page instance with reddit page opened
        """

        self.click(
            page_instance,
            ".header-user-dropdown",
        )

        # It's normal not to find it, sometimes there is none :shrug:
        self.click(
            page_instance,
            "button >> span:has-text('Settings')",
        )

        self.click(
            page_instance,
            "button >> span:has-text('Dark Mode')",
        )

        # Closes settings
        self.click(
            page_instance,
            ".header-user-dropdown"
        )

    def __close_nsfw(
            self,
            page_instance: Page,
    ) -> None:
        """
        Closes NSFW stuff

        Args:
            page_instance:  Instance of main page
        """

        print_substep("Post is NSFW. You are spicy...")

        # Triggers indirectly reload
        self.click(
            page_instance,
            "button:has-text('Yes')",
            {"timeout": 5000},
        )

        # indirect reload
        page_instance.wait_for_load_state()

        self.click(
            page_instance,
            "button:has-text('Click to see nsfw')",
            {"timeout": 5000},
        )

    def __collect_comment(
            self,
            comment_obj: dict,
            filename_idx: int,
    ) -> None:
        """
        Makes a screenshot of the comment

        Args:
            comment_obj: prew comment object
            filename_idx: index for the filename
        """
        comment_page = self.context.new_page()
        comment_page.goto(
            f'https://reddit.com{comment_obj["comment_url"]}',
            timeout=0,  # Fix for Navigation TimeoutError
        )

        # Translates submission' comment
        if self.post_lang:
            comment_tl = ts.google(
                comment_obj["comment_body"],
                to_language=self.post_lang,
            )
            comment_page.evaluate(
                '([comment_id, comment_tl]) => document.querySelector(`#t1_${comment_id} > div:nth-child(2) > div > div[data-testid="comment"] > div`).textContent = comment_tl',  # noqa
                [comment_obj["comment_id"], comment_tl],
            )

        self.screenshot(
            comment_page,
            f"id=t1_{comment_obj['comment_id']}",
            {"path": f"assets/temp/png/comment_{filename_idx}.png"},
        )

    # WIP  TODO test it
    def __collect_story(
            self,
            main_page: Page,
    ):
        # Translates submission text
        if self.post_lang:
            story_tl = ts.google(
                self.reddit_object["thread_post"],
                to_language=self.post_lang,
            )
            split_story_tl = story_tl.split('\n')

            main_page.evaluate(
                "(split_story_tl) => split_story_tl.map(function(element, i) { return [element, document.querySelectorAll('[data-test-id=\"post-content\"] > [data-click-id=\"text\"] > div > p')[i]]; }).forEach(mappedElement => mappedElement[1].textContent = mappedElement[0])",  # noqa
                split_story_tl,
            )

        self.screenshot(
            main_page,
            "//div[@data-test-id='post-content']//div[@data-click-id='text']",
            {"path": "assets/temp/png/story_content.png"},
        )

    def download(
            self,
    ):
        """
        Downloads screenshots of reddit posts as seen on the web. Downloads to assets/temp/png
        """
        print_step("Downloading screenshots of reddit posts...")

        print_substep("Launching Headless Browser...")
        self.get_browser()

        # ! Make sure the reddit screenshots folder exists
        Path("assets/temp/png").mkdir(parents=True, exist_ok=True)

        # Get the thread screenshot
        reddit_main = self.context.new_page()
        reddit_main.goto(  # noqa
            self.reddit_object["thread_url"],
            timeout=0,  # Fix for Navigation TimeoutError
        )

        if settings.config["settings"]["theme"] == "dark":
            self.__dark_theme(reddit_main)

        if self.reddit_object["is_nsfw"]:
            # This means the post is NSFW and requires to click the proceed button.
            self.__close_nsfw(reddit_main)

        # Translates submission title
        if self.post_lang:
            print_substep("Translating post...")
            texts_in_tl = ts.google(
                self.reddit_object["thread_title"],
                to_language=self.post_lang,
            )

            reddit_main.evaluate(
                f"(texts_in_tl) => document.querySelector('[data-test-id=\"post-content\"] > div:nth-child(3) > div > div').textContent = texts_in_tl",  # noqa
                texts_in_tl,
            )
        else:
            print_substep("Skipping translation...")

        # No sense to move it to common.py
        async_tasks_primary = (  # noqa
            [
                self.__collect_comment(self.reddit_object["comments"][idx], idx) for idx in
                self.screenshot_idx
            ]
            if not self.story_mode
            else [
                self.__collect_story(reddit_main)
            ]
        )

        async_tasks_primary.append(
            self.screenshot(
                reddit_main,
                f"id=t3_{self.reddit_object['thread_id']}",
                {"path": "assets/temp/png/title.png"},
            )
        )

        for idx, chunked_tasks in enumerate(
                [chunk for chunk in common.chunks(async_tasks_primary, 10)],
                start=1,
        ):
            chunk_list = async_tasks_primary.__len__() // 10 + (1 if async_tasks_primary.__len__() % 10 != 0 else 0)
            for task in track(
                    as_completed(chunked_tasks),
                    description=f"Downloading comments: Chunk {idx}/{chunk_list}",
                    total=chunked_tasks.__len__(),
            ):
                print("-")

        print_substep("Comments downloaded Successfully.", style="bold green")
        self.close_browser()
