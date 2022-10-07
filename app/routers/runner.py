import os,sys,importlib
import time
import uuid
from datetime import datetime
from typing import Dict, List, Text

try:
    import allure

    ALLURE = allure
except ModuleNotFoundError:
    ALLURE = None

from loguru import logger

from httprunner.client import HttpSession
from httprunner.config import Config
from httprunner.exceptions import ParamsError, ValidationFailure
from httprunner.loader import load_project_meta
from httprunner.models import (
    ProjectMeta,
    StepResult,
    TConfig,
    TestCaseInOut,
    TestCaseSummary,
    TestCaseTime,
    VariablesMapping,
)
from httprunner.parser import Parser
from httprunner.utils import LOGGER_FORMAT, merge_variables
from httprunner.make import main_make


class SessionRunner(object):
    config: Config
    teststeps: List[object]  # list of Step

    parser: Parser = None
    session: HttpSession = None
    case_id: Text = ""
    root_dir: Text = ""
    thrift_client = None
    db_engine = None

    __config: TConfig
    __project_meta: ProjectMeta = None
    __export: List[Text] = []
    __step_results: List[StepResult] = []
    __session_variables: VariablesMapping = {}
    __is_referenced: bool = False
    # time
    __start_at: float = 0
    __duration: float = 0
    # log
    __log_path: Text = ""

    def __init(self):
        self.__config = self.config.struct()
        self.__session_variables = self.__session_variables or {}
        self.__start_at = 0
        self.__duration = 0
        self.__is_referenced = self.__is_referenced or False

        self.__project_meta = self.__project_meta or load_project_meta(
            self.__config.path
        )
        self.case_id = self.case_id or str(uuid.uuid4())
        self.root_dir = self.root_dir or self.__project_meta.RootDir
        self.__log_path = os.path.join(self.root_dir, "logs", f"{self.case_id}.run.log")

        self.__step_results = self.__step_results or []
        self.session = self.session or HttpSession()
        self.parser = self.parser or Parser(self.__project_meta.functions)

    def with_session(self, session: HttpSession) -> "SessionRunner":
        self.session = session
        return self

    def get_config(self) -> TConfig:
        return self.__config

    def set_referenced(self) -> "SessionRunner":
        self.__is_referenced = True
        return self

    def with_case_id(self, case_id: Text) -> "SessionRunner":
        self.case_id = case_id
        return self

    def with_variables(self, variables: VariablesMapping) -> "SessionRunner":
        self.__session_variables = variables
        return self

    def with_export(self, export: List[Text]) -> "SessionRunner":
        self.__export = export
        return self

    def with_thrift_client(self, thrift_client) -> "SessionRunner":
        self.thrift_client = thrift_client
        return self

    def with_db_engine(self, db_engine) -> "SessionRunner":
        self.db_engine = db_engine
        return self

    def __parse_config(self, param: Dict = None) -> None:
        # parse config variables
        self.__config.variables.update(self.__session_variables)
        if param:
            self.__config.variables.update(param)
        self.__config.variables = self.parser.parse_variables(self.__config.variables)

        # parse config name
        self.__config.name = self.parser.parse_data(
            self.__config.name, self.__config.variables
        )

        # parse config base url
        self.__config.base_url = self.parser.parse_data(
            self.__config.base_url, self.__config.variables
        )

    def get_export_variables(self) -> Dict:
        # override testcase export vars with step export
        export_var_names = self.__export or self.__config.export
        export_vars_mapping = {}
        for var_name in export_var_names:
            if var_name not in self.__session_variables:
                raise ParamsError(
                    f"failed to export variable {var_name} from session variables {self.__session_variables}"
                )

            export_vars_mapping[var_name] = self.__session_variables[var_name]

        return export_vars_mapping

    def get_summary(self) -> TestCaseSummary:
        """get testcase result summary"""
        start_at_timestamp = self.__start_at
        start_at_iso_format = datetime.utcfromtimestamp(start_at_timestamp).isoformat()

        summary_success = True
        for step_result in self.__step_results:
            if not step_result.success:
                summary_success = False
                break

        return TestCaseSummary(
            name=self.__config.name,
            success=summary_success,
            case_id=self.case_id,
            time=TestCaseTime(
                start_at=self.__start_at,
                start_at_iso_format=start_at_iso_format,
                duration=self.__duration,
            ),
            in_out=TestCaseInOut(
                config_vars=self.__config.variables,
                export_vars=self.get_export_variables(),
            ),
            log=self.__log_path,
            step_results=self.__step_results,
        )

    def merge_step_variables(self, variables: VariablesMapping) -> VariablesMapping:
        # override variables
        # step variables > extracted variables from previous steps
        variables = merge_variables(variables, self.__session_variables)
        # step variables > testcase config variables
        variables = merge_variables(variables, self.__config.variables)

        # parse variables
        return self.parser.parse_variables(variables)

    def __run_step(self, step):
        """run teststep, step maybe any kind that implements IStep interface

        Args:
            step (Step): teststep

        """
        logger.info(f"run step begin: {step.name()} >>>>>>")

        # run step
        for i in range(step.retry_times + 1):
            try:
                if ALLURE is not None:
                    with ALLURE.step(f"step: {step.name()}"):
                        step_result: StepResult = step.run(self)
                else:
                    step_result: StepResult = step.run(self)
                break
            except ValidationFailure:
                if i == step.retry_times:
                    raise
                else:
                    logger.warning(
                        f"run step {step.name()} validation failed,wait {step.retry_interval} sec and try again"
                    )
                    time.sleep(step.retry_interval)
                    logger.info(
                        f"run step retry ({i + 1}/{step.retry_times} time): {step.name()} >>>>>>"
                    )

        # save extracted variables to session variables
        self.__session_variables.update(step_result.export_vars)
        # update testcase summary
        self.__step_results.append(step_result)

        logger.info(f"run step end: {step.name()} <<<<<<\n")

    def test_start(self, param: Dict = None) -> "SessionRunner":
        """main entrance, discovered by pytest"""
        print("\n")
        self.__init()
        self.__parse_config(param)

        if ALLURE is not None and not self.__is_referenced:
            # update allure report meta
            ALLURE.dynamic.title(self.__config.name)
            ALLURE.dynamic.description(f"TestCase ID: {self.case_id}")

        logger.info(
            f"Start to run testcase: {self.__config.name}, TestCase ID: {self.case_id}"
        )

        logger.add(self.__log_path, format=LOGGER_FORMAT, level="DEBUG")
        self.__start_at = time.time()
        try:
            # run step in sequential order
            for step in self.teststeps:
                self.__run_step(step)
        finally:
            logger.info(f"generate testcase log: {self.__log_path}")
            if ALLURE is not None:
                ALLURE.attach.file(
                    self.__log_path,
                    name="all log",
                    attachment_type=ALLURE.attachment_type.TEXT,
                )

        self.__duration = time.time() - self.__start_at
        return self

        #-------------------------------------------------------------------------------------------#
    def run_test_start(self, root_path, case_path):
        # 生成py用例
        main_make([os.path.join(root_path, case_path)]) # (testcase_py_path = main_make(testcase_json_path)[0]py用例的绝对路径信息)
        # py用例文件名、类名处理
        case_path_list = case_path.split("\\") # 拆分用例相对路径
        testcase_class_name =  f"TestCase{case_path_list[-1].replace('.json','').title()}" # 按照httprunner规则生成py用例 类名
        testcase_pag_name = case_path_list[-1].replace(".json","_test") # 按照httprunner规则生成py用例 文件名
        # 导入py用例包
        sys.path.append(root_path) # 添加脚本工程路径，以便导入
        testcase_pag_path = ".".join(case_path_list[0:-1])+"."+testcase_pag_name # 用例相对路径转化为 包路径
        pag = importlib.import_module(testcase_pag_path) # 导入py用例所在的包
        testcase_class_name_obj = getattr(pag, testcase_class_name) # 获取包下的 类对象
        # 执行py用例
        runner = testcase_class_name_obj().test_start() # 实例化用例对象，并执行py用例
        summary = runner.get_summary() # 获取执行结果
        return summary

    def init_run(self,testcase_obj):
        self.__config = testcase_obj.config
        self.__project_meta = load_project_meta(self.__config.path)
        self.parser = self.parser or Parser(self.__project_meta.functions)
        self.__start_at = 0
        self.__duration = 0
        self.case_id = str(uuid.uuid4())
        self.root_dir = self.__project_meta.RootDir
        self.__log_path = os.path.join(self.root_dir, "logs", f"{self.case_id}.run.log")
        self.__step_results = []
        self.session = self.session or HttpSession()
        self.__session_variables = {} 

    def parse_config_variables(self,param):
        self.__parse_config(param)

    def result_dispose(self,step_result):
        self.__session_variables.update(step_result.export_vars)
        self.__step_results.append(step_result)

    def start_time(self):
        self.__start_at = time.time() 

    def total_time(self):
        self.__duration = time.time() - self.__start_at
    #-------------------------------------------------------------------------------------------#


class HttpRunner(SessionRunner):
    # split SessionRunner to keep consistent with golang version
    pass
