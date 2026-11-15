"""runner の入口（REST）。

`POST /runs` で命令を受け、実行が終わるまで待って結果を返す。
1 台の PC の画面で本物のアプリを動かすので、実行は一度に一つだけ受ける。
実行中に次の命令が来たら、待たずに 409（`runner_busy`）で断る。
"""

import threading
from typing import Any, Protocol

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from qata_runner.contract_check import problems
from qata_runner.contracts.runner_command_schema import RunnerCommand
from qata_runner.contracts.runner_result_schema import RunnerResult


class Operator(Protocol):
    def run(self, command: RunnerCommand) -> RunnerResult: ...


def create_app(operator: Operator) -> FastAPI:
    app = FastAPI(title="qata-runner")
    running = threading.Lock()

    @app.post("/runs")
    async def run(request: Request) -> Any:
        # 命令は FastAPI で検証せず、親の契約（JSON Schema）で判定する
        try:
            body = await request.json()
        except ValueError:
            return _invalid_command(["本文が JSON として読めない"])
        found = problems("runner-command.schema.json", body)
        if found:
            return _invalid_command(found)
        command = RunnerCommand.model_validate(body)
        # 待たせると、server が待つのをやめたあとに動き出して
        # 次の実行と重なるので、待たずに断る
        if not running.acquire(blocking=False):
            return _error(
                409, "runner_busy", "ほかの実行の最中なので受けない。終わってから送る"
            )
        try:
            # 本物の操作は終わるまで待つので、スレッドで動かす
            result = await run_in_threadpool(operator.run, command)
        finally:
            running.release()
        return result.model_dump(mode="json", exclude_none=True)

    return app


def _invalid_command(found: list[str]) -> JSONResponse:
    return _error(422, "invalid_command", "命令が契約に合わない：" + "／".join(found))


def _error(status: int, code: str, message: str) -> JSONResponse:
    # 形は契約の共通の部品 error（code・message）
    return JSONResponse(status_code=status, content={"code": code, "message": message})
