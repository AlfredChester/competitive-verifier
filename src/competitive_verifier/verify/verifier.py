import datetime
import pathlib
import subprocess
import time
from abc import ABC, abstractmethod
from functools import cached_property
from logging import getLogger
from typing import Iterable, Optional, Protocol

from competitive_verifier import github, log
from competitive_verifier.download.main import run_impl as run_download
from competitive_verifier.error import VerifierError
from competitive_verifier.exec import exec_command
from competitive_verifier.models import (
    ResultStatus,
    VerificationFile,
    VerificationFileResult,
    VerificationInput,
    VerificationResult,
)
from competitive_verifier.verify.resource import ulimit_stack
from competitive_verifier.verify.split_state import SplitState

logger = getLogger(__name__)


class InputContainer(ABC):
    @property
    @abstractmethod
    def input(self) -> VerificationInput:
        ...


class InputResolver(InputContainer):
    @cached_property
    def verification_files(self) -> dict[pathlib.Path, VerificationFile]:
        """
        List of verification files.
        """
        return {p: f for p, f in self.input.files.items() if f.is_verification()}


class Verifier(InputResolver):
    use_git_timestamp: bool
    timeout: float
    default_tle: float
    prev_result: Optional[VerificationResult]
    split_state: Optional[SplitState]

    _result: Optional[VerificationResult]
    verification_time: datetime.datetime

    def __init__(
        self,
        input: VerificationInput,
        *,
        use_git_timestamp: bool,
        timeout: float,
        default_tle: float,
        prev_result: Optional[VerificationResult],
        split_state: Optional[SplitState],
        verification_time: Optional[datetime.datetime] = None,
    ) -> None:
        self._input = input
        self.prev_result = prev_result
        self.use_git_timestamp = use_git_timestamp
        self.timeout = timeout
        self.default_tle = default_tle
        self.split_state = split_state
        self.verification_time = verification_time or datetime.datetime.now()
        self._result = None

    @property
    def input(self) -> VerificationInput:
        return self._input

    @property
    def force_result(self) -> VerificationResult:
        if self._result is None:
            raise VerifierError("Not verified yet.")
        return self._result

    def is_updated_file(self, file_result: VerificationFileResult) -> bool:
        return file_result.is_updated(
            min(self.verification_time, self.get_current_timestamp(file_result.path))
        )

    def is_success(self) -> bool:
        if self._result is None:
            return False
        return all(
            fr.command_result != ResultStatus.FAILURE for fr in self._result.files
        )

    def get_current_timestamp(self, path: pathlib.Path) -> datetime.datetime:
        if self.use_git_timestamp:
            return github.get_commit_time(self.input.resolve_dependencies(path))
        else:
            dependicies = self.input.resolve_dependencies(path)

            timestamp = max(x.stat().st_mtime for x in dependicies)
            system_local_timezone = (
                datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
            )
            return datetime.datetime.fromtimestamp(
                timestamp, tz=system_local_timezone
            ).replace(
                microsecond=0
            )  # microsecond=0 is required because it's erased in git commit

    @cached_property
    def remaining_verification_files(self) -> list[VerificationFile]:
        """
        List of verification files that have not yet been verified.
        """
        verification_files: Iterable[VerificationFile] = self.verification_files

        if self.prev_result is None:
            return verification_files

        not_updated_files = set(
            r.path for r in self.prev_result.files if not self.is_updated_file(r)
        )
        verification_files = (
            f for f in verification_files if f.path not in not_updated_files
        )
        return [f for f in verification_files if f.path not in not_updated_files]

    @cached_property
    def current_verification_files(self) -> list[VerificationFile]:
        """
        List of verification files that self should verify.

        if ``split_state`` is None the property is ``remaining_verification_files``;

        else ``split_state.split(remaining_verification_files)``.
        """
        if self.split_state is None:
            return self.remaining_verification_files

        return self.split_state.split(self.remaining_verification_files)

    def exec_pre_commands(self):
        pre_commands = self.input.pre_command
        if pre_commands:
            logger.info("pre_command size %d", len(pre_commands))
            for cmd in pre_commands:
                try:
                    logger.debug("pre_command: %s", cmd)
                    exec_command(cmd, check=True, group_log=True)
                except subprocess.CalledProcessError:
                    logger.error("Failed to pre_command: %s", cmd)
                    raise
        else:
            logger.info("There is no pre_command")

    def verify(self, *, download: bool = True) -> VerificationResult:
        start_time = datetime.datetime.now()

        if download:
            run_download(self.input)

        logger.info(
            "current_verification_files: %s",
            " ".join(str(f.path) for f in self.current_verification_files),
        )
        try:
            ulimit_stack()
        except Exception:
            logger.warning("failed to increase the stack size[ulimit]")

        self.exec_pre_commands()

        files = list[VerificationFileResult]()
        for f in self.current_verification_files:
            prev_time = datetime.datetime.now()
            if (
                self.timeout is not None
                and (prev_time - start_time).total_seconds() > self.timeout
            ):
                logger.warning("Skip[Timeout]: %s", f)
                continue

            logger.info("Start: %s", str(f.path))
            with log.group(f"Verify: {str(f.path)}", use_stderr=True):
                logger.debug(repr(f))

            #     ok = verify_file(f)
            #     finish_time = datetime.datetime.now()
            #     if ok:
            #         success_time = finish_time
            #     else:
            #         success_time = None
            #         github.print_error(
            #             "Failed to verify",
            #             file=str(
            #                 f.path.resolve(strict=True).relative_to(
            #                     pathlib.Path.cwd().resolve(strict=True)
            #                 )
            #             ),
            #         )

        #     logger.info(
        #         "Finish verify: total time = %f seconds, %s",
        #         (finish_time - prev_time).total_seconds(),
        #         f,
        #     )

        #     # files.append(
        #     #     VerificationFileResult(
        #     #         f.path,
        #     #         last_success_time=success_time,
        #     #     )
        #     # )

        self._result = VerificationResult(files=files)
        return self._result


def verify_file(file: VerificationFile) -> bool:
    time.sleep(0.2)
    return False
