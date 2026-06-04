-- init_db.sql — Day 04 TravelBot seed schema
-- Runs once on first Postgres container start.
-- Idempotent: all statements use IF NOT EXISTS / ON CONFLICT DO NOTHING.

-- ── Bookings ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bookings (
    booking_id      VARCHAR(20)  PRIMARY KEY,
    passenger_name  VARCHAR(100) NOT NULL,
    flight_number   VARCHAR(20)  NOT NULL,
    origin          VARCHAR(50)  NOT NULL,
    destination     VARCHAR(50)  NOT NULL,
    departure_date  DATE         NOT NULL,
    seat_class      VARCHAR(20)  NOT NULL DEFAULT 'Economy',
    status          VARCHAR(20)  NOT NULL DEFAULT 'Confirmed',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ── Flights ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS flights (
    flight_number    VARCHAR(20) NOT NULL,
    airline          VARCHAR(50) NOT NULL,
    origin           VARCHAR(50) NOT NULL,
    origin_code      VARCHAR(10) NOT NULL,
    destination      VARCHAR(50) NOT NULL,
    destination_code VARCHAR(10) NOT NULL,
    departure_time   TIME        NOT NULL,
    arrival_time     TIME        NOT NULL,
    duration_min     INTEGER     NOT NULL,
    seat_class       VARCHAR(20) NOT NULL DEFAULT 'Economy',
    price_usd        NUMERIC(10,2) NOT NULL,
    available_seats  INTEGER     NOT NULL DEFAULT 100,
    PRIMARY KEY (flight_number, seat_class)
);

-- ── Durable conversation history ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS session_history (
    id          BIGSERIAL    PRIMARY KEY,
    session_id  VARCHAR(100) NOT NULL,
    user_id     VARCHAR(100) NOT NULL,
    role        VARCHAR(20)  NOT NULL,   -- 'user' | 'model'
    content     TEXT         NOT NULL,
    tool_calls  JSONB,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sh_session ON session_history (session_id, created_at);

-- ── Booking seed data ─────────────────────────────────────────────────────
INSERT INTO bookings (booking_id, passenger_name, flight_number, origin, destination, departure_date, seat_class, status)
VALUES
    ('TB-1001', 'Priya Sharma',  'AI-204', 'Mumbai',    'London',    '2026-07-15', 'Economy',  'Confirmed'),
    ('TB-1002', 'Ravi Patel',    'SQ-422', 'Singapore', 'Tokyo',     '2026-07-20', 'Business', 'Confirmed'),
    ('TB-1003', 'Aisha Mehta',   'EK-501', 'Dubai',     'Paris',     '2026-06-30', 'Economy',  'Cancelled'),
    ('TB-1004', 'James Liu',     'AI-204', 'Mumbai',    'London',    '2026-07-15', 'Business', 'Confirmed'),
    ('TB-1005', 'Maria Santos',  'SQ-422', 'Singapore', 'Tokyo',     '2026-08-01', 'Economy',  'Pending'),
    ('TB-1006', 'Kenji Tanaka',  'AI-302', 'Delhi',     'Singapore', '2026-07-10', 'Economy',  'Confirmed'),
    ('TB-1007', 'Fatima Al-Ali', 'QR-501', 'Doha',      'Bangkok',   '2026-07-25', 'Economy',  'Confirmed')
ON CONFLICT (booking_id) DO NOTHING;

-- ── Flight seed data ──────────────────────────────────────────────────────
INSERT INTO flights (flight_number, airline, origin, origin_code, destination, destination_code, departure_time, arrival_time, duration_min, seat_class, price_usd, available_seats)
VALUES
    -- AI-204: Mumbai → London (Economy + Business)
    ('AI-204', 'Air India',        'Mumbai',    'BOM', 'London',    'LHR', '14:35', '19:50', 545,  'Economy',  420.00,  82),
    ('AI-204', 'Air India',        'Mumbai',    'BOM', 'London',    'LHR', '14:35', '19:50', 545,  'Business', 1850.00,  8),

    -- SQ-422: Singapore → Tokyo (Economy + Business)
    ('SQ-422', 'Singapore Air',    'Singapore', 'SIN', 'Tokyo',     'NRT', '08:20', '16:35', 435,  'Economy',  380.00,  65),
    ('SQ-422', 'Singapore Air',    'Singapore', 'SIN', 'Tokyo',     'NRT', '08:20', '16:35', 435,  'Business', 2100.00, 12),

    -- EK-501: Dubai → Paris
    ('EK-501', 'Emirates',         'Dubai',     'DXB', 'Paris',     'CDG', '02:10', '06:20', 430,  'Economy',  510.00, 110),
    ('EK-501', 'Emirates',         'Dubai',     'DXB', 'Paris',     'CDG', '02:10', '06:20', 430,  'Business', 2400.00, 16),

    -- AI-302: Delhi → Singapore
    ('AI-302', 'Air India',        'Delhi',     'DEL', 'Singapore', 'SIN', '10:00', '19:30', 330,  'Economy',  290.00,  95),
    ('AI-302', 'Air India',        'Delhi',     'DEL', 'Singapore', 'SIN', '10:00', '19:30', 330,  'Business', 980.00,  10),

    -- QR-501: Doha → Bangkok
    ('QR-501', 'Qatar Airways',    'Doha',      'DOH', 'Bangkok',   'BKK', '03:45', '13:10', 325,  'Economy',  340.00, 130),
    ('QR-501', 'Qatar Airways',    'Doha',      'DOH', 'Bangkok',   'BKK', '03:45', '13:10', 325,  'Business', 1560.00, 20)
ON CONFLICT (flight_number, seat_class) DO NOTHING;
