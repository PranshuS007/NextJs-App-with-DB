ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'member';
ALTER TABLE class_sessions ADD COLUMN IF NOT EXISTS max_size INTEGER NOT NULL DEFAULT 12;
ALTER TABLE class_sessions ADD COLUMN IF NOT EXISTS timezone TEXT NOT NULL DEFAULT 'America/Los_Angeles';
ALTER TABLE class_sessions ADD COLUMN IF NOT EXISTS cancellation_deadline_hours INTEGER NOT NULL DEFAULT 12;

CREATE TABLE IF NOT EXISTS class_occurrences (
    id BIGSERIAL PRIMARY KEY,
    class_session_id BIGINT NOT NULL REFERENCES class_sessions(id) ON DELETE CASCADE,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    timezone TEXT NOT NULL,
    max_size INTEGER NOT NULL CHECK (max_size > 0),
    status TEXT NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'cancelled')),
    cancelled_by BIGINT REFERENCES users(id),
    cancelled_at TIMESTAMPTZ,
    cancellation_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (class_session_id, starts_at)
);

CREATE TABLE IF NOT EXISTS bookings (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    class_occurrence_id BIGINT NOT NULL REFERENCES class_occurrences(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('confirmed', 'waitlisted', 'cancelled', 'class_cancelled')),
    waitlist_position INTEGER,
    cancelled_at TIMESTAMPTZ,
    cancellation_reason TEXT,
    promoted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_active_booking_per_user_occurrence ON bookings (user_id, class_occurrence_id) WHERE status IN ('confirmed', 'waitlisted');
CREATE INDEX IF NOT EXISTS idx_bookings_occurrence_status ON bookings (class_occurrence_id, status, waitlist_position, created_at);
CREATE INDEX IF NOT EXISTS idx_class_occurrences_starts_at ON class_occurrences (starts_at, status);

CREATE TABLE IF NOT EXISTS email_notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    email TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed')),
    error TEXT,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_email_notifications_status ON email_notifications (status, created_at);
