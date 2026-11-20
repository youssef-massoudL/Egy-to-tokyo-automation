"""The post caption for X and Instagram: one fixed line per edition (the user's words, 20 Nov 2026).

Change the words here and both platforms follow on the next run. Slack keeps its own line (cloud/slack_notify.py).
X refuses a post whose text repeats a recent one, so cloud/x_post.py adds the date on a second line only if X says so.
Usage: python cloud/caption.py egx|us   prints the caption, posts nothing.
"""
import sys

CAPTION = {
    "egx": "من القاهرة لطوكيو.. نبض أسواق المال في مكان واحد | الرادار",
    "us": "من لندن ل نيويورك.. نبض أسواق المال في مكان واحد | الرادار",
}


def build(name, site=None):
    return {"instagram": CAPTION[name], "x": CAPTION[name]}


if __name__ == "__main__":
    print(build(sys.argv[1])["x"])
