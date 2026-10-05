from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.sdk.resources import Resource
from azure.appconfiguration.provider import load
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
config = load(
    endpoint="https://documind-appconfig-nna2005.azconfig.io",
    credential=credential,
)

configure_azure_monitor(
    connection_string=config["Documind:AppInsightsConnectionString"],
    resource=Resource.create({"service.name": "documind-func"}),
)

