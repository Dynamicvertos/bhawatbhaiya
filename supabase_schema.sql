-- ==============================================================================
-- NCB DIGITAL COMPANION FOR FIELD DRUG TESTING (Problem ID: 26231)
-- SUPABASE POSTGRESQL SCHEMA & STORAGE CONFIGURATION
-- ==============================================================================

-- 1. Create the main field drug tests table
CREATE TABLE IF NOT EXISTS public.field_drug_tests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_id_display TEXT NOT NULL,                     -- e.g. "NCB-2026-FDT-9821"
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    operator_id TEXT NOT NULL,                         -- Badge / Officer ID e.g. "NCB-DEL-4091"
    operator_name TEXT DEFAULT 'Field Officer',
    
    -- Chemical Reagent & Classification
    reagent_id TEXT NOT NULL,                          -- e.g. "marquis", "scott", "duquenois_levine"
    reagent_name TEXT NOT NULL,                        -- e.g. "Marquis Reagent"
    target_drug_class TEXT NOT NULL,                   -- e.g. "Opiates / Amphetamines"
    detected_substance TEXT NOT NULL,                  -- e.g. "Heroin / Morphine Presumptive"
    result_category TEXT NOT NULL CHECK (result_category IN ('POSITIVE', 'NEGATIVE', 'INCONCLUSIVE')),
    confidence_score NUMERIC(5,2) NOT NULL,            -- e.g. 96.50
    delta_e_metric NUMERIC(6,2),                       -- CIE Delta E 2000 color distance
    explanation TEXT,
    
    -- Forensic & Lighting Calibration Metadata
    calibration_method TEXT DEFAULT 'ARUCO_REFERENCE_CARD', -- 'ARUCO_REFERENCE_CARD' or 'AUTO_WHITE_BALANCE'
    card_detected BOOLEAN DEFAULT FALSE,
    raw_sample_hex TEXT,                              -- Observed Hex color before calibration
    calibrated_sample_hex TEXT,                       -- Calibrated Hex color
    expected_standard_hex TEXT,                       -- Reference standard target Hex
    
    -- Chain of Custody & Evidence Tamper-Proofing
    image_sha256 TEXT NOT NULL,                       -- 64-char SHA-256 of raw image bytes
    digital_signature TEXT,                           -- HMAC signature anchoring test + hash
    
    -- Geolocation & Environment
    gps_latitude DOUBLE PRECISION,
    gps_longitude DOUBLE PRECISION,
    location_address TEXT,
    device_info TEXT,
    
    -- URLs for media stored in Supabase Storage or Local
    image_url TEXT,
    certificate_url TEXT,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Performance Indexes for the Searchable Field Log
CREATE INDEX IF NOT EXISTS idx_fdt_timestamp ON public.field_drug_tests(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_fdt_operator_id ON public.field_drug_tests(operator_id);
CREATE INDEX IF NOT EXISTS idx_fdt_result_category ON public.field_drug_tests(result_category);
CREATE INDEX IF NOT EXISTS idx_fdt_reagent_id ON public.field_drug_tests(reagent_id);
CREATE INDEX IF NOT EXISTS idx_fdt_image_sha256 ON public.field_drug_tests(image_sha256);

-- 3. Enable Row Level Security (RLS)
ALTER TABLE public.field_drug_tests ENABLE ROW LEVEL SECURITY;

-- 4. Policies (Public read and insert for the mobile companion app)
CREATE POLICY "Allow public read access to test logs"
    ON public.field_drug_tests FOR SELECT
    USING (true);

CREATE POLICY "Allow authenticated and anon insert for field tests"
    ON public.field_drug_tests FOR INSERT
    WITH CHECK (true);

-- ==============================================================================
-- STORAGE BUCKETS SETUP INSTRUCTIONS:
-- In the Supabase Dashboard:
-- 1. Go to "Storage" -> "New bucket"
-- 2. Create bucket named: `drug-test-images` (make it Public)
-- 3. Create bucket named: `drug-test-certificates` (make it Public)
-- ==============================================================================

