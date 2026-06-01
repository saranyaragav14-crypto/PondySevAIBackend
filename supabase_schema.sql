-- PondySevAi Database Schema
-- Run this in your Supabase SQL editor to set up all tables

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─────────────────────────────────────────
-- DEPARTMENTS
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS departments (
    id TEXT PRIMARY KEY,
    name_en TEXT NOT NULL,
    name_ta TEXT NOT NULL,
    name_fr TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO departments (id, name_en, name_ta, name_fr) VALUES
    ('law_order',   'Law & Order / Traffic',         'சட்டம் & ஒழுங்கு / போக்குவரத்து', 'Ordre public / Circulation'),
    ('education',   'Education',                      'கல்வி',                              'Éducation'),
    ('health_san',  'Health & Sanitation',            'சுகாதாரம் & சுத்தம்',               'Santé & Hygiène'),
    ('environment', 'Environment & Coastal',          'சுற்றுச்சூழல் & கடலோரம்',          'Environnement & Littoral'),
    ('tourism',     'Tourism & Cultural Events',      'சுற்றுலா & கலாச்சார நிகழ்வுகள்',  'Tourisme & Événements culturels'),
    ('disaster',    'Disaster Management',            'பேரிடர் மேலாண்மை',                  'Gestion des catastrophes'),
    ('municipal',   'Municipal & Administration',     'மாநகராட்சி & நிர்வாகம்',           'Administration municipale'),
    ('women_child', 'Women & Child Welfare',          'பெண்கள் & குழந்தை நலன்',           'Femmes & Protection de l''enfance')
ON CONFLICT (id) DO NOTHING;

-- ─────────────────────────────────────────
-- ROLES
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    dept_id TEXT REFERENCES departments(id),
    dept_name TEXT,
    qualifications TEXT,
    description TEXT,
    demand TEXT CHECK (demand IN ('low', 'medium', 'high')) DEFAULT 'low',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO roles (id, name, dept_id, dept_name, qualifications, demand) VALUES
    ('r01','Traffic assistant','law_order','Law & Order / Traffic','Physical fitness, Tamil, basic road rules','high'),
    ('r02','Parking management','law_order','Law & Order / Traffic','Spatial awareness, crowd handling','medium'),
    ('r03','Pedestrian safety guide','law_order','Law & Order / Traffic','Communication, visibility awareness','medium'),
    ('r04','Crowd control officer','law_order','Law & Order / Traffic','NSS/NCC experience preferred, team coordination','high'),
    ('r05','Emergency lane coordinator','law_order','Law & Order / Traffic','Quick decision-making, physical fitness','high'),
    ('r06','Teaching assistant (primary)','education','Education','10th/+2 minimum, Tamil/English fluency','low'),
    ('r07','Adult literacy facilitator','education','Education','Patience, Tamil literacy, basic teaching','low'),
    ('r08','Digital literacy trainer','education','Education','Computer basics, can teach seniors','low'),
    ('r09','Library support volunteer','education','Education','Organisation, Tamil/English reading','low'),
    ('r10','Health camp registration aide','health_san','Health & Sanitation','Data entry, Tamil communication','low'),
    ('r11','Blood donation drive coordinator','health_san','Health & Sanitation','Health awareness, empathy','low'),
    ('r12','Vaccination camp helper','health_san','Health & Sanitation','Ability to follow medical staff direction','low'),
    ('r13','First aid support (events)','health_san','Health & Sanitation','First aid certification required','medium'),
    ('r14','Beach cleaning drive volunteer','environment','Environment & Coastal','Physical fitness, outdoor tolerance','high'),
    ('r15','Mangrove plantation aide','environment','Environment & Coastal','Physical fitness, outdoor work','high'),
    ('r16','Waste segregation educator','environment','Environment & Coastal','Awareness of waste categories','medium'),
    ('r17','Tourist information guide','tourism','Tourism & Cultural Events','English + Tamil, French preferred, Pondy history','low'),
    ('r18','Heritage walk assistant','tourism','Tourism & Cultural Events','Knowledge of French Quarter, history','low'),
    ('r19','Bastille Day event volunteer','tourism','Tourism & Cultural Events','Crowd management, French language a plus','medium'),
    ('r20','Pongal/cultural event coordinator','tourism','Tourism & Cultural Events','Cultural event experience, Tamil','medium'),
    ('r21','Cyclone preparedness volunteer','disaster','Disaster Management','Basic disaster training','medium'),
    ('r22','Flood relief distribution aide','disaster','Disaster Management','Physical strength, logistics coordination','high'),
    ('r23','Voter awareness campaign volunteer','municipal','Municipal & Administration','Communication, Tamil fluency','low'),
    ('r24','Census data collection aide','municipal','Municipal & Administration','Numeracy, house-to-house visits','medium'),
    ('r25','Senior citizen welfare visitor','municipal','Municipal & Administration','Empathy, patience, elder care','low'),
    ('r26','Anganwadi support volunteer','women_child','Women & Child Welfare','Child care awareness, Tamil','low'),
    ('r27','Women SHG facilitator','women_child','Women & Child Welfare','Community organisation experience','low')
ON CONFLICT (id) DO NOTHING;

-- ─────────────────────────────────────────
-- VOLUNTEERS
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS volunteers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reference_number TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    dob DATE,
    phone TEXT UNIQUE NOT NULL,
    email TEXT,
    commune TEXT NOT NULL CHECK (commune IN ('Puducherry','Villianur','Bahour','Ariyankuppam')),
    address TEXT,
    gender TEXT,
    languages TEXT[] DEFAULT '{}',
    qualifications TEXT[] DEFAULT '{}',
    availability TEXT[] DEFAULT '{}',
    mobility_impairment BOOLEAN DEFAULT FALSE,
    experience TEXT,
    departments TEXT[] DEFAULT '{}',
    motivation TEXT,
    role_type TEXT,
    status TEXT DEFAULT 'registered'
        CHECK (status IN ('registered','pending_review','assigned','rejected','active','inactive')),
    assigned_role TEXT,
    assigned_dept TEXT,
    assigned_by UUID,
    rejected_by UUID,
    tier TEXT CHECK (tier IN ('bronze','silver','gold','platinum')),
    ai_assessment TEXT,
    ai_score FLOAT,
    ai_top_matches JSONB,
    latest_feedback TEXT CHECK (latest_feedback IN ('top_performer','performer','regular')),
    nodal_officer_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- STAFF (nodal officers + admins)
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS staff (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('nodal_officer','admin')),
    commune TEXT,
    department TEXT,
    phone TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- DEPLOYMENTS
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS deployments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    volunteer_id UUID REFERENCES volunteers(id),
    role_id TEXT REFERENCES roles(id),
    location TEXT NOT NULL,
    scheduled_date DATE NOT NULL,
    shift TEXT NOT NULL,
    status TEXT DEFAULT 'scheduled'
        CHECK (status IN ('scheduled','active','completed','cancelled')),
    checked_in_at TIMESTAMPTZ,
    checked_out_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- FEEDBACK
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    volunteer_id UUID REFERENCES volunteers(id),
    deployment_id UUID REFERENCES deployments(id),
    category TEXT NOT NULL CHECK (category IN ('top_performer','performer','regular')),
    notes TEXT,
    submitted_by UUID REFERENCES staff(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- CERTIFICATES
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS certificates (
    id TEXT PRIMARY KEY,
    volunteer_id UUID REFERENCES volunteers(id),
    tier TEXT NOT NULL,
    issued_date TIMESTAMPTZ DEFAULT NOW(),
    verify_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- ROW LEVEL SECURITY
-- ─────────────────────────────────────────
ALTER TABLE volunteers ENABLE ROW LEVEL SECURITY;
ALTER TABLE deployments ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE certificates ENABLE ROW LEVEL SECURITY;

-- Allow service role full access (used by FastAPI backend)
CREATE POLICY "service_role_all" ON volunteers FOR ALL USING (true);
CREATE POLICY "service_role_all" ON deployments FOR ALL USING (true);
CREATE POLICY "service_role_all" ON feedback FOR ALL USING (true);
CREATE POLICY "service_role_all" ON certificates FOR ALL USING (true);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER volunteers_updated_at
    BEFORE UPDATE ON volunteers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ─────────────────────────────────────────
-- INDEXES for performance
-- ─────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_volunteers_phone ON volunteers(phone);
CREATE INDEX IF NOT EXISTS idx_volunteers_status ON volunteers(status);
CREATE INDEX IF NOT EXISTS idx_volunteers_commune ON volunteers(commune);
CREATE INDEX IF NOT EXISTS idx_deployments_volunteer ON deployments(volunteer_id);
CREATE INDEX IF NOT EXISTS idx_certificates_volunteer ON certificates(volunteer_id);
