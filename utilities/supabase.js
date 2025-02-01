import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = 'https://kketfaaihwjflpdngtvo.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtrZXRmYWFpaHdqZmxwZG5ndHZvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzczMTg1MTAsImV4cCI6MjA1Mjg5NDUxMH0.PYKJKO39GCAXm-3zDFnQbSy1-oc4iuE4neLnfItIC90';

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

export default supabase;
