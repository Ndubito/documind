import time
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

credential = DefaultAzureCredential()
client = SecretClient(
    vault_url="https://documind-kv-nna2005.vault.azure.net/",
    credential=credential,
)

_cache = {}
CACHE_TTL_SECONDS = 300  # 5 minutes — arbitrary, chosen for freshness vs. call volume

def get_cached_secret(name: str) -> str:
    now = time.time()
    if name in _cache:
        value, fetched_at = _cache[name]
        if now - fetched_at < CACHE_TTL_SECONDS:
            return value
    value = client.get_secret(name).value
    _cache[name] = (value, now)
    return value
