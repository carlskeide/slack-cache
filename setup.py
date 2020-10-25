from setuptools import setup

__version__ = "1.1.0"
__url__ = "https://github.com/carlskeide/slack-cache"

setup(
    name="slack-cache",
    version=__version__,
    description="Cached Slack API",
    author="Carl Skeide",
    author_email="carl@skeide.se",
    license="MIT",
    keywords=[
        "slack"
    ],
    py_modules=[
        "slack_cache"
    ],
    include_package_data=False,
    zip_safe=False,
    url=__url__,
    download_url="{}/archive/{}.tar.gz".format(__url__, __version__),
    install_requires=[
        "slackclient >= 2.0",
        "redis >= 3.5"
    ]
)
