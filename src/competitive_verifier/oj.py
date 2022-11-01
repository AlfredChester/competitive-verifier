import hashlib
import os
from logging import getLogger

import onlinejudge._implementation.utils
import onlinejudge.utils
import onlinejudge_command.main
import onlinejudge_command.subcommand.download
from onlinejudge.service.yukicoder import YukicoderService
from onlinejudge.type import NotLoggedInError

import competitive_verifier.config
from competitive_verifier import log

oj_cache_dir = (
    competitive_verifier.config.cache_dir.resolve(strict=False) / "online-judge-tools"
)
onlinejudge._implementation.utils.user_cache_dir = oj_cache_dir
logger = getLogger(__name__)


def is_yukicoder(url: str) -> bool:
    return YukicoderService.from_url(url) is not None


def download(url: str) -> None:
    directory = (
        competitive_verifier.config.cache_dir / hashlib.md5(url.encode()).hexdigest()
    )

    if not (directory / "test").exists() or list((directory / "test").iterdir()) == []:
        with log.group(f"download: {url}", use_stderr=True):
            logger.info("download: %s", url)
            directory.mkdir(parents=True, exist_ok=True)
            # time.sleep(2)

            arg_list = [
                "--cookie",
                str(oj_cache_dir / "cookie.txt"),
                "download",
                "--system",
                "-d",
                str(directory / "test"),
                "--silent",
                url,
            ]

            YUKICODER_TOKEN = os.environ.get("YUKICODER_TOKEN")
            if YUKICODER_TOKEN:
                arg_list += ["--yukicoder-token", YUKICODER_TOKEN]

            try:
                parser = onlinejudge_command.main.get_parser()  # type: ignore
                args = parser.parse_args(arg_list)  # type: ignore
                onlinejudge_command.subcommand.download.run(args)  # type: ignore
            except Exception as e:
                if isinstance(e, NotLoggedInError) and is_yukicoder(url):
                    logger.error("Requied: $YUKICODER_TOKEN environment variable")
                else:
                    logger.error(e)
    else:
        logger.info("already exists: %s", url)
