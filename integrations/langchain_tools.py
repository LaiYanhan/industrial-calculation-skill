"""Optional LangChain adapter with the same schemas and calculation boundary."""

from typing import TYPE_CHECKING, Any, Callable

from integrations.service import IndustrialToolService, TOOL_DEFINITIONS

if TYPE_CHECKING:
    from langchain_core.tools import StructuredTool


def get_langchain_tools(service: IndustrialToolService | None = None) -> list["StructuredTool"]:
    from langchain_core.tools import StructuredTool

    facade = service if service is not None else IndustrialToolService()

    def bind(name: str) -> Callable[..., dict[str, Any]]:
        def invoke(**arguments: Any) -> dict[str, Any]:
            return facade.invoke(name, arguments)
        return invoke

    return [
        StructuredTool.from_function(
            func=bind(definition.name),
            name=definition.name,
            description=definition.description,
            args_schema=definition.arguments_model,
        )
        for definition in TOOL_DEFINITIONS
    ]
