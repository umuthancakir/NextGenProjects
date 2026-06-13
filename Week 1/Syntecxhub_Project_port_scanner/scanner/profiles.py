"""
Named scan profiles — each is a preset combination of engine parameters.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Profile:
    name:        str
    ports:       str
    timeout:     float
    concurrency: int
    randomize:   bool
    delay:       float
    banner_grab: bool
    use_nvd:     bool
    description: str


PROFILES: dict[str, Profile] = {
    'quick': Profile(
        name='quick',
        ports='top100',
        timeout=0.5,
        concurrency=1000,
        randomize=False,
        delay=0.0,
        banner_grab=True,
        use_nvd=False,
        description='Top 100 ports, 500ms timeout. Fast discovery with banner grab.',
    ),
    'full': Profile(
        name='full',
        ports='top1000',
        timeout=1.0,
        concurrency=500,
        randomize=False,
        delay=0.0,
        banner_grab=True,
        use_nvd=True,
        description='Top 1000 ports, 1s timeout, NVD lookups. Thorough assessment.',
    ),
    'stealth': Profile(
        name='stealth',
        ports='top100',
        timeout=2.0,
        concurrency=30,
        randomize=True,
        delay=0.15,
        banner_grab=True,
        use_nvd=False,
        description=(
            'Slow, randomized, low-concurrency scan. Reduces IDS/IPS detection '
            'probability by spreading traffic over time and varying port order. '
            'Much slower than other profiles.'
        ),
    ),
    'security': Profile(
        name='security',
        ports='security',
        timeout=1.5,
        concurrency=300,
        randomize=False,
        delay=0.0,
        banner_grab=True,
        use_nvd=True,
        description=(
            'Security-focused port list: includes all top-100 plus high-risk '
            'ports (Redis, MongoDB, Elasticsearch, Docker API, Memcached, etc.) '
            'with NVD lookups.'
        ),
    ),
    'web': Profile(
        name='web',
        ports='80,443,8000,8008,8080,8081,8443,8888,3000,4000,4443,5000,9000,9090,9443',
        timeout=1.5,
        concurrency=200,
        randomize=False,
        delay=0.0,
        banner_grab=True,
        use_nvd=True,
        description='Web service ports only. Good for auditing web-facing infrastructure.',
    ),
    'db': Profile(
        name='db',
        ports='1433,1521,3306,5432,5984,6379,6380,7474,9042,9200,11211,27017,27018,28017,50070',
        timeout=1.5,
        concurrency=100,
        randomize=False,
        delay=0.0,
        banner_grab=True,
        use_nvd=True,
        description=(
            'Database and data store ports. Checks for internet-exposed databases '
            '(MySQL, PostgreSQL, Redis, MongoDB, Elasticsearch, Memcached, etc.)'
        ),
    ),
}

DEFAULT_PROFILE = 'quick'


def get(name: str) -> Optional[Profile]:
    return PROFILES.get(name)


def list_profiles() -> list[Profile]:
    return list(PROFILES.values())
