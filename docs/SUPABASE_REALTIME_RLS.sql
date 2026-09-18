-- MAINTAIN AI Supabase Realtime authorization
-- Run this in Supabase SQL Editor after Supabase Auth is configured.
-- Neon remains the system of record; Supabase app_metadata carries only the
-- server-assigned organization routing claim used by Realtime RLS.

create policy "maintain ai org telemetry read"
on realtime.messages
for select
to authenticated
using (
  realtime.topic() = 'org:' ||
    (auth.jwt() -> 'app_metadata' ->> 'organization_id') ||
    ':telemetry'
);

-- The browser never inserts Realtime broadcasts. FastAPI publishes them with
-- SUPABASE_SECRET_KEY, so no client INSERT policy is required.
