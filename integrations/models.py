"""Shared transport arguments. Physical units come from scenario manifests."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

NonEmptyString = Annotated[str, Field(min_length=1)]
SolutionMode = Literal["AUTO", "FORWARD", "INVERSE", "SEARCH"]


class ToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class ListScenariosArguments(ToolArguments):
    """No parameters are needed for discovery."""


class ScenarioSpecArguments(ToolArguments):
    scenario_id: NonEmptyString = Field(description="场景 ID；先调用 industrial_list_scenarios 查询。")


class ParameterValue(ToolArguments):
    name: NonEmptyString = Field(description="规范参数名或受支持别名，见场景规范。")
    value: float = Field(
        strict=True,
        allow_inf_nan=False,
        description="有限数值；必须使用该参数的 canonical_unit，禁止附带单位字符串。",
    )


class CalculateArguments(ScenarioSpecArguments):
    inputs: list[ParameterValue] = Field(
        description="已知参数列表。必须严格使用场景规范定义的数值，严禁自行联网搜索或主观估算；缺参会返回 INTERRUPTED。"
    )
    targets: list[NonEmptyString] | None = Field(
        default=None, description="反解目标规范名列表；常规正解填 null。"
    )
    solution_mode: SolutionMode = Field(default="AUTO", description="AUTO 自动识别正解或反解。")
    generate_excel: bool = Field(
        default=False, description="true 在执行主机 exports/ 生成报表；默认 false。"
    )

    @model_validator(mode="after")
    def reject_duplicate_names(self) -> "CalculateArguments":
        names = [parameter.name for parameter in self.inputs]
        if len(names) != len(set(names)):
            raise ValueError("inputs 中同一参数名只能出现一次")
        return self
