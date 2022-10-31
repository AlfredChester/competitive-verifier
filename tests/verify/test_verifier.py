# pyright: reportPrivateUsage=none
import datetime
from pathlib import Path
from typing import Optional

import pytest

from competitive_verifier.models.command import VerificationCommand
from competitive_verifier.models.file import VerificationFile, VerificationInput
from competitive_verifier.models.result import (
    FileVerificationResult,
    VerificationResult,
)
from competitive_verifier.verify.util import VerifyError
from competitive_verifier.verify.verifier import SplitState, Verifier


def get_verifier(
    input: VerificationInput = VerificationInput(files=[]),
    *,
    use_git_timestamp: bool = True,
    timeout: float = 60,
    default_tle: float = 60,
    prev_result: Optional[VerificationResult] = None,
    split_state: Optional[SplitState] = None,
    verification_time: Optional[datetime.datetime] = None,
) -> Verifier:
    return Verifier(
        input=input,
        use_git_timestamp=use_git_timestamp,
        timeout=timeout,
        default_tle=default_tle,
        prev_result=prev_result,
        split_state=split_state,
        verification_time=verification_time,
    )


def test_force_result():
    verifier = get_verifier()
    verifier._result = VerificationResult(files=[])
    assert verifier.force_result is verifier._result


def test_force_result_failue():
    verifier = get_verifier()
    with pytest.raises(VerifyError) as e:
        _ = verifier.force_result

    assert e.value.message == "Not verified yet."


def test_verification_files():
    def get_verification_file(path_str: str) -> VerificationFile:
        return VerificationFile(
            Path(path_str),
            dependencies=[],
            verification=VerificationCommand(command="true"),
        )

    foo_baz = get_verification_file("foo/baz.py")
    foo_abc = get_verification_file("foo/abc.py")
    baz_foo = get_verification_file("baz/foo.py")
    hoge_piyo = get_verification_file("hoge/piyo.py")
    hoge_hoge = get_verification_file("hoge/hoge.py")
    verifier = get_verifier(
        input=VerificationInput(
            files=[
                foo_baz,
                foo_abc,
                baz_foo,
                hoge_piyo,
                hoge_hoge,
            ]
        ),
    )
    assert verifier.verification_files == [
        baz_foo,
        foo_abc,
        foo_baz,
        hoge_hoge,
        hoge_piyo,
    ]


def test_remaining_verification_files():
    def get_verification_file(path_str: str) -> VerificationFile:
        return VerificationFile(
            Path(path_str),
            dependencies=[],
            verification=VerificationCommand(command="true"),
        )

    foo_baz = get_verification_file("foo/baz.py")
    foo_abc = get_verification_file("foo/abc.py")
    baz_foo = get_verification_file("baz/foo.py")
    hoge_piyo = get_verification_file("hoge/piyo.py")
    hoge_hoge = get_verification_file("hoge/hoge.py")
    verifier = VerifierForIsSuccessTest(
        VerificationResult(files=[]),
        VerificationInput(
            files=[
                baz_foo,
                foo_abc,
                foo_baz,
                hoge_hoge,
                hoge_piyo,
            ]
        ),
        verification_time=datetime.datetime(2020, 2, 27, 19, 0, 0),
        default_current_timestamp=datetime.datetime(2019, 12, 25, 19, 0, 0),
        current_timestamp_dict={
            Path("hoge/piyo.py"): datetime.datetime(2019, 12, 28, 19, 0, 0),
            Path("hoge/hoge.py"): datetime.datetime(2019, 12, 27, 19, 0, 0),
        },
        prev_result=VerificationResult(
            files=[
                FileVerificationResult(
                    baz_foo.path,
                    last_success_time=None,
                ),
                FileVerificationResult(
                    hoge_hoge.path,
                    last_success_time=datetime.datetime(2019, 12, 27, 19, 0, 0),
                ),
                FileVerificationResult(
                    hoge_piyo.path,
                    last_success_time=datetime.datetime(2019, 12, 27, 19, 0, 0),
                ),
            ]
        ),
    )
    print([str(f.path) for f in verifier.remaining_verification_files])
    assert verifier.remaining_verification_files == [
        baz_foo,
        foo_abc,
        foo_baz,
        hoge_piyo,
    ]


class VerifierForIsSuccessTest(Verifier):
    def __init__(
        self,
        result: VerificationResult,
        input: VerificationInput = VerificationInput(files=[]),
        *,
        use_git_timestamp: bool = True,
        timeout: float = 60,
        default_tle: float = 60,
        prev_result: Optional[VerificationResult] = None,
        split_state: Optional[SplitState] = None,
        verification_time: datetime.datetime,
        default_current_timestamp: datetime.datetime,
        current_timestamp_dict: dict[Path, datetime.datetime],
    ) -> None:
        super().__init__(
            input=input,
            use_git_timestamp=use_git_timestamp,
            timeout=timeout,
            default_tle=default_tle,
            prev_result=prev_result,
            split_state=split_state,
            verification_time=verification_time,
        )
        self._result = result
        self.default_current_timestamp = default_current_timestamp
        self.current_timestamp_dict = current_timestamp_dict

    def get_current_timestamp(self, path: Path) -> datetime.datetime:
        return self.current_timestamp_dict.get(path, self.default_current_timestamp)


def test_is_success():
    def get_result(path: str) -> FileVerificationResult:
        return FileVerificationResult(
            Path(path),
            last_success_time=datetime.datetime(2017, 9, 20, 18, 0, 0),
        )

    res = VerificationResult(
        files=[
            get_result("lib/bar.py"),
            get_result("lib/baz.py"),
            get_result("lib/hoge.py"),
            get_result("lib/fuga.py"),
            get_result("test/1.py"),
            get_result("test/2.py"),
            get_result("test/3.py"),
            get_result("test/4.py"),
        ]
    )
    verifier = VerifierForIsSuccessTest(
        res,
        verification_time=datetime.datetime(2017, 9, 20, 18, 0, 1),
        default_current_timestamp=datetime.datetime(2016, 12, 24, 18, 36, 45),
        current_timestamp_dict={},
    )
    assert verifier.is_success()

    verifier = VerifierForIsSuccessTest(
        res,
        verification_time=datetime.datetime(2017, 9, 20, 18, 0, 1),
        default_current_timestamp=datetime.datetime(2019, 12, 24, 18, 36, 45),
        current_timestamp_dict={},
    )
    assert not verifier.is_success()

    verifier = VerifierForIsSuccessTest(
        res,
        verification_time=datetime.datetime(2017, 9, 20, 18, 0, 1),
        default_current_timestamp=datetime.datetime(2016, 12, 24, 18, 36, 45),
        current_timestamp_dict={
            Path("test/1.py"): datetime.datetime(2018, 12, 24, 18, 36, 45),
        },
    )
    assert not verifier.is_success()
