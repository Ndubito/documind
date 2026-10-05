from azure.appconfiguration.provider import load, AzureAppConfigurationKeyVaultOptions
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()

config = load(
    endpoint="https://documind-appconfig-nna2005.azconfig.io",
    credential=credential,
    key_vault_options=AzureAppConfigurationKeyVaultOptions(credential=credential),
)

connection_string = config["DocuMind:PostgresConnectionString"]  # resolved transparently

