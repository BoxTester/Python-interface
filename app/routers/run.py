from fastapi import APIRouter
import os
from loguru import logger

from httprunner import HttpRunner
from httprunner.models import StepResult
from httprunner.loader import load_testcase_file
from httprunner.parser import parse_parameters
from httprunner.step_request import run_step_request


router = APIRouter()
runner = HttpRunner()

@router.post("/hrun/run_test_start", tags=["run"])
async def run_test_start(testcase_infos: list):
    resp = {
        "code": 200,
        "message": "success",
        "results": []
    }
    root_path = r"C:\Users\95439\hrp4demo" # 脚本工程路径
    for testcase_info in testcase_infos:
        case_path = testcase_info.get("case_path") # json用例相对路径
        testcase_json_path = os.path.join(root_path,case_path) # json用例绝对路径
        if os.path.exists(testcase_json_path):
            # 执行用例
            summary = runner.run_test_start(root_path, case_path)
            if not summary.success:
                resp["code"] = 300
                resp["message"] = "httprunner执行异常"
            result = {"result":summary,"caseID":testcase_info.get("caseID"),"case_path":case_path}
            resp["results"].append(result)
        else:
            resp["code"] = 400
            resp["message"] = f"路径不存在:{testcase_json_path}"
    return resp

@router.post("/hrun/run_hrun", tags=["run"])
async def run_hrun(testcase_infos: list):
    resp = {
        "code": 200,
        "message": "success",
        "results": []
    }
    # root_path = r"C:\Users\95439\hrp4demo" # 脚本工程路径
    root_path = r"C:\Users\Zhao\demo"
    for testcase_info in testcase_infos:
        case_path = testcase_info.get("case_path") # 获取json用例相对路径
        testcase_json_path = os.path.join(root_path,case_path) # json用例绝对路径
        if os.path.exists(testcase_json_path):
            # 执行用例
            summary = run_hrun(root_path, case_path)
            # if not summary.success:
            #     resp["code"] = 300
            #     resp["message"] = "httprunner执行异常"
            result = {"result":summary,"caseID":testcase_info.get("caseID"),"case_path":case_path}
            resp["results"].append(result)
        else:
            resp["code"] = 400
            resp["message"] = f"路径不存在:{testcase_json_path}"
    return resp

def run_hrun(root_path,case_path):

    testcase_obj = load_testcase_file(os.path.join(root_path,case_path))

    testcase_step_summary = {}

    def request_step(step_runner,step,param):
        logger.info(f"run step begin: {step.name} >>>>>>")
        step_runner.parse_config_variables(param)
        step_result: StepResult = run_step_request(step_runner,step)
        step_runner.result_dispose(step_result)
        logger.info(f"run step end: {step.name} <<<<<<\n")

    def testcase_step(step):

        def testcase_request_step(testcase_step_runner, step_testcase_obj, param):
            logger.info(f"run testcase_step begin: {testcase_step_runner.get_config().name}")
            testcase_step_runner.start_time()
            for step in step_testcase_obj.teststeps:
                if step.testcase:
                    testcase_step_summary.update({step.name:f"不支持步骤引用用例嵌套用例，请调整: {step.testcase}"})
                if step.request:
                    request_step(testcase_step_runner,step,param)
                    testcase_step_summary.update(testcase_step_runner.get_summary())
            testcase_step_runner.total_time()
            logger.info(f"run testcase_step end: {testcase_step_runner.get_config().name}")

        step_testcase_obj = load_testcase_file(os.path.join(root_path,step.testcase))
        testcase_step_runner = HttpRunner()
        testcase_step_runner.init_run(step_testcase_obj)
        if step_testcase_obj.config.parameters:
            params = parse_parameters(step_testcase_obj.config.parameters)
            for param in params:
                testcase_request_step(testcase_step_runner, step_testcase_obj, param)
        else:
            param = {}
            testcase_request_step(testcase_step_runner, step_testcase_obj, param)
   
    def run_step(param):
        logger.info(f"Start to run testcase: {runner.get_config().name}")
        runner.start_time()
        for step in testcase_obj.teststeps:
            if step.request:
                request_step(runner,step,param)
            if step.testcase:
                testcase_step(step)
        runner.total_time()
        logger.info(f"Finished running testcase: {runner.get_config().name}")
        
    runner.init_run(testcase_obj)
    if runner.get_config().parameters:
        params = parse_parameters(runner.get_config().parameters)
        for param in params:
            run_step(param)
    else:
        param = {}
        run_step(param)

    testcase_summary = runner.get_summary()

    return testcase_summary,testcase_step_summary

if __name__ == "__main__":
    testcase_infos = [{"case_path":"testcases\\a.json","caseID":"case00001"}]
    # root_path = r"C:\Users\95439\hrp4demo"
    root_path = r"C:\Users\Zhao\demo"
    case_path = testcase_infos[0].get("case_path")
    run_hrun(root_path,case_path)

