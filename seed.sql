INSERT INTO instructors (name, bio)
VALUES ('Maya Bennett', '500-hour registered yoga teacher specializing in Hatha, Vinyasa, Yin, and restorative practices.')
ON CONFLICT DO NOTHING;

INSERT INTO yoga_styles (name, description, level, duration_minutes, display_order)
VALUES
('Hatha', 'A steady, alignment-focused practice with time to explore each shape. Grounding and accessible.', 'All levels', 60, 1),
('Vinyasa', 'A fluid practice linking breath with movement. Creative, energizing, and thoughtfully paced.', 'Open level', 60, 2),
('Yin', 'Long-held, floor-based shapes that invite release, mobility, and deep quiet.', 'All levels', 75, 3)
ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description, level = EXCLUDED.level, duration_minutes = EXCLUDED.duration_minutes, display_order = EXCLUDED.display_order;

INSERT INTO class_sessions (style_id, instructor_id, title, day_of_week, start_time, duration_minutes, display_order)
SELECT ys.id, i.id, seed.title, seed.day_of_week, seed.start_time::time, seed.duration_minutes, seed.display_order
FROM (VALUES
('Vinyasa', 'Morning Vinyasa', 1, '07:00', 60, 1),
('Hatha', 'Grounded Hatha', 2, '17:30', 60, 2),
('Vinyasa', 'Slow Flow', 3, '18:00', 60, 3),
('Hatha', 'Gentle Hatha', 5, '09:00', 60, 4),
('Yin', 'Yin + Restore', 0, '17:00', 75, 5)
) AS seed(style_name, title, day_of_week, start_time, duration_minutes, display_order)
JOIN yoga_styles ys ON ys.name = seed.style_name
JOIN instructors i ON i.name = 'Maya Bennett'
WHERE NOT EXISTS (SELECT 1 FROM class_sessions cs WHERE cs.title = seed.title AND cs.day_of_week = seed.day_of_week);

INSERT INTO pricing_plans (slug, name, description, unit_amount_cents, currency, is_featured, display_order)
VALUES
('drop-in', 'Drop-in', 'One class · use anytime', 2200, 'usd', FALSE, 1),
('five-pack', '5 Class Pack', '$19 per class · valid 3 months', 9500, 'usd', TRUE, 2),
('ten-pack', '10 Class Pack', '$17 per class · valid 6 months', 17000, 'usd', FALSE, 3)
ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, unit_amount_cents = EXCLUDED.unit_amount_cents, currency = EXCLUDED.currency, is_featured = EXCLUDED.is_featured, display_order = EXCLUDED.display_order;

INSERT INTO blog_categories (name)
VALUES ('Movement'), ('Breathwork'), ('Practice')
ON CONFLICT (name) DO NOTHING;

INSERT INTO blog_posts (category_id, slug, title, excerpt, body, read_time_minutes, image_class, is_featured, published_at)
SELECT bc.id, seed.slug, seed.title, seed.excerpt, seed.body, seed.read_time_minutes, seed.image_class, seed.is_featured, NOW()
FROM (VALUES
('Movement', 'simple-morning-stretches-for-a-calm-start', 'Simple Morning Stretches for a Calm Start', 'A few quiet minutes of movement can change the texture of your whole day. Try this gentle sequence before the noise begins.', 'Begin seated at the edge of your bed. Let your shoulders soften and take three unhurried breaths. Circle your wrists and ankles, then reach both arms overhead and lean gently to each side.\n\nCome to hands and knees for a few rounds of cat and cow. Move slowly enough to notice where the breath naturally leads. Finish in a comfortable forward fold, knees soft, before rolling up to stand.', 5, 'blog-one', TRUE),
('Breathwork', 'breathing-techniques-for-stress-relief', 'Breathing Techniques for Stress Relief', 'Your breath is always available as a path back to steadiness.', 'Try breathing in for a count of four and out for a count of six. Repeat for two minutes without forcing the breath. A slightly longer exhale gently signals the nervous system that it is safe to settle.', 4, 'blog-two', FALSE),
('Practice', 'why-consistency-in-yoga-matters', 'Why Consistency in Yoga Matters', 'A small practice you return to often can be more powerful than an occasional long one.', 'Consistency builds familiarity: with the shapes, with your breath, and with yourself. Set a modest rhythm you can keep—even ten minutes twice a week—and let the practice grow naturally from there.', 6, 'blog-three', FALSE)
) AS seed(category_name, slug, title, excerpt, body, read_time_minutes, image_class, is_featured)
JOIN blog_categories bc ON bc.name = seed.category_name
ON CONFLICT (slug) DO UPDATE SET title = EXCLUDED.title, excerpt = EXCLUDED.excerpt, body = EXCLUDED.body, read_time_minutes = EXCLUDED.read_time_minutes, image_class = EXCLUDED.image_class, is_featured = EXCLUDED.is_featured, published_at = EXCLUDED.published_at;

UPDATE class_sessions
SET max_size = 12,
    timezone = 'America/Los_Angeles',
    cancellation_deadline_hours = 12;

INSERT INTO class_occurrences (class_session_id, starts_at, ends_at, timezone, max_size)
SELECT cs.id,
       ((next_dates.class_date + cs.start_time) AT TIME ZONE cs.timezone) AS starts_at,
       ((next_dates.class_date + cs.start_time + (cs.duration_minutes || ' minutes')::interval) AT TIME ZONE cs.timezone) AS ends_at,
       cs.timezone,
       cs.max_size
FROM class_sessions cs
CROSS JOIN LATERAL (
    SELECT (CURRENT_DATE + ((cs.day_of_week - EXTRACT(DOW FROM CURRENT_DATE)::int + offset_days + 7) % 7))::date AS class_date
    FROM generate_series(0, 21, 7) AS offset_days
) next_dates
WHERE cs.is_active = TRUE
ON CONFLICT (class_session_id, starts_at) DO UPDATE
SET ends_at = EXCLUDED.ends_at,
    timezone = EXCLUDED.timezone,
    max_size = EXCLUDED.max_size;
