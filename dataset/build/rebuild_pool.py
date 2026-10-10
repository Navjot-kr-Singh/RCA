"""Rebuild the incident pool from every statuspage harvest. No import side effects."""
import json, re, html, os

NICE = {'npmjs': 'npm', 'circleci': 'CircleCI', 'travis-ci': 'Travis CI',
        'traviscistatus': 'Travis CI', 'githubstatus': 'GitHub', 'gitlab': 'GitLab',
        'mongodb': 'MongoDB Atlas', 'cockroachlabs': 'CockroachDB',
        'digitalocean': 'DigitalOcean', 'openai': 'OpenAI', 'hubspot': 'HubSpot',
        '1password': '1Password', 'clickup': 'ClickUp', 'bigcommerce': 'BigCommerce',
        'livekit': 'LiveKit', 'assemblyai': 'AssemblyAI', 'elevenlabs': 'ElevenLabs',
        'planetscale': 'PlanetScale', 'clickhouse': 'ClickHouse',
        'influxdata': 'InfluxData', 'sumologic': 'Sumo Logic', 'newrelic': 'New Relic',
        'pagerduty': 'PagerDuty', 'launchdarkly': 'LaunchDarkly', 'sendgrid': 'SendGrid',
        'messagebird': 'MessageBird', 'gocardless': 'GoCardless',
        'squarespace': 'Squarespace', 'bitbucket': 'Bitbucket', 'jfrog': 'JFrog',
        'hashicorp': 'HashiCorp', 'cloudamqp': 'CloudAMQP', 'vercel': 'Vercel',
        'redditstatus': 'Reddit', 'issquareup': 'Square', 'buildkitestatus': 'Buildkite',
        'cloudflarestatus': 'Cloudflare', 'shopifystatus': 'Shopify',
        'contentfulstatus': 'Contentful', 'neonstatus': 'Neon', 'dockerstatus': 'Docker',
        'fastlystatus': 'Fastly', 'monday': 'Monday.com', 'auth0': 'Auth0',
        'flyio': 'Fly.io', 'imgix': 'imgix', 'enomstatus': 'Enom',
        'wandb': 'Weights & Biases', 'duo': 'Duo Security', 'crunchydata': 'Crunchy Data',
        'browserstack': 'BrowserStack', 'lambdatest': 'LambdaTest',
        'saucelabs': 'Sauce Labs', 'stackblitz': 'StackBlitz', 'codesandbox': 'CodeSandbox',
        'posthog': 'PostHog', 'paloaltonetworks': 'Palo Alto Networks',
        'crowdstrike': 'CrowdStrike', 'sentinelone': 'SentinelOne',
        'lemonsqueezy': 'Lemon Squeezy', 'chargebee': 'Chargebee', 'avalara': 'Avalara',
        'taxjar': 'TaxJar', 'greenhouse': 'Greenhouse', 'rabbitmq': 'RabbitMQ',
        'couchbase': 'Couchbase', 'mariadb': 'MariaDB', 'percona': 'Percona'}


def strip_html(h):
    t = re.sub(r'<[^>]+>', ' ', h or '')
    t = html.unescape(t)
    return re.sub(r'\s+', ' ', t).strip()


def org_of(host):
    h = host.lower()
    h = re.sub(r'^(www|api)\.', '', h)
    h = re.sub(r'\.statuspage\.io$', '', h)
    h = re.sub(r'^status\.', '', h)
    h = re.sub(r'\.(com|io|co|net|org|dev|ai|app|cloud|tech|us|so|me|tv|uk|sh)$', '', h)
    h = re.sub(r'\.(com|io|co|net|org)$', '', h)
    h = h.split('.')[0]
    h = re.sub(r'status$', '', h)
    return NICE.get(h, h.capitalize() if h.islower() else h)


def shape(host, org, inc):
    ups = inc.get('incident_updates', []) or []
    body = ' || '.join(strip_html(u.get('body')) for u in ups if u.get('body'))
    pm = [strip_html(u.get('body')) for u in ups
          if (u.get('status') == 'postmortem'
              or 'postmortem' in strip_html(u.get('body', ''))[:200].lower())]
    return {'org': org, 'host': host, 'inc_id': inc['id'], 'name': inc.get('name'),
            'impact': inc.get('impact'), 'created_at': inc.get('created_at'),
            'resolved_at': inc.get('resolved_at'),
            'url': f"https://{host}/incidents/{inc['id']}",
            'postmortem': ' || '.join(pm)[:6000], 'body': body[:8000]}


def main():
    pool = {}
    # harvest 1 is already in shaped form
    h1 = json.load(open('raw/statuspage.json'))
    for host, v in h1.items():
        for inc in v['incidents']:
            pool.setdefault(inc['inc_id'], inc)
    n1 = len(pool)
    print(f'  statuspage.json      -> {n1}')
    # every later harvest holds the raw statuspage payloads; pick them all up
    import glob
    files = sorted(glob.glob('raw/statuspage*_raw.json'),
                   key=lambda p: int(re.search(r'statuspage(\d+)_raw', p).group(1)))
    for f in files:
        if not os.path.exists(f):
            print(f'  {f} MISSING')
            continue
        before = len(pool)
        for host, v in json.load(open(f)).items():
            org = v.get('org') or org_of(host)
            for inc in v['raw'].get('incidents', []):
                if not inc.get('id') or inc['id'] in pool:
                    continue
                pool[inc['id']] = shape(host, org, inc)
        print(f'  {os.path.basename(f):<22} -> +{len(pool)-before} (total {len(pool)})')
    json.dump(list(pool.values()), open('raw/pool_all.json', 'w'))
    print('POOL TOTAL:', len(pool), '| orgs:', len(set(p['org'] for p in pool.values())))


if __name__ == '__main__':
    main()
