CREATE TABLE IF NOT EXISTS quota (
    day TEXT PRIMARY KEY,
    connection_requests INTEGER NOT NULL DEFAULT 0,
    messages INTEGER NOT NULL DEFAULT 0,
    profile_views INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS icp (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    titles TEXT,           -- JSON array
    seniorities TEXT,      -- JSON array
    industries TEXT,       -- JSON array
    company_sizes TEXT,    -- JSON array
    geographies TEXT,      -- JSON array
    keywords TEXT,         -- JSON array
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS prospects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT UNIQUE,
    urn_id TEXT,
    full_name TEXT,
    headline TEXT,
    company TEXT,
    title TEXT,
    location TEXT,
    industry TEXT,
    score REAL,
    raw TEXT,              -- JSON blob
    icp_id INTEGER REFERENCES icp(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'new',  -- new|queued|connected|replied|converted|excluded
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    icp_id INTEGER REFERENCES icp(id) ON DELETE SET NULL,
    channel TEXT NOT NULL DEFAULT 'linkedin',
    status TEXT NOT NULL DEFAULT 'draft',  -- draft|active|paused|done
    connection_template TEXT,
    followup_templates TEXT,  -- JSON array of {delay_hours, body}
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS campaign_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER REFERENCES campaigns(id) ON DELETE CASCADE,
    prospect_id INTEGER REFERENCES prospects(id) ON DELETE CASCADE,
    step TEXT NOT NULL,  -- connect|followup_1|followup_2|...
    status TEXT NOT NULL DEFAULT 'pending',  -- pending|sent|failed|skipped
    run_after TEXT,
    sent_at TEXT,
    error TEXT,
    UNIQUE(campaign_id, prospect_id, step)
);

CREATE TABLE IF NOT EXISTS scheduled_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    visibility TEXT DEFAULT 'ANYONE',
    run_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled',  -- scheduled|published|failed
    published_at TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id INTEGER REFERENCES prospects(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,   -- job_change|funding|post_engagement|mutual_connection
    payload TEXT,         -- JSON
    detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
    processed INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_prospects_icp ON prospects(icp_id);
CREATE INDEX IF NOT EXISTS idx_prospects_status ON prospects(status);
CREATE INDEX IF NOT EXISTS idx_steps_run_after ON campaign_steps(run_after);
CREATE INDEX IF NOT EXISTS idx_posts_run_at ON scheduled_posts(run_at, status);

-- TikTok Shop / external brand leads imported from CSV
CREATE TABLE IF NOT EXISTS brand_leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_name TEXT UNIQUE NOT NULL,
    kalodata_url TEXT,
    tiktok_profile TEXT,
    website TEXT,
    amazon_url TEXT,
    linkedin_company TEXT,       -- LinkedIn company entityUrn numeric ID (populated by find_brand_contacts)
    lead_status TEXT NOT NULL DEFAULT 'new',
    welcome_message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_brand_leads_status ON brand_leads(lead_status);
CREATE INDEX IF NOT EXISTS idx_brand_leads_linkedin ON brand_leads(linkedin_company);
