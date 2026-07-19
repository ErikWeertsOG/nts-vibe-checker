export type NtsLink = { label: string; url: string };

export type Category = "RESIDENT" | "NTS-PRESENCE" | "NTS-VIBE" | "ADJACENT" | "OFF";

export type Set = {
  day: string;         // "2026-08-21"
  stage: string;       // "ALPHA" | "BRAVO" | "HEINEKEN" | "LIMA" | "INDIA" | "X-RAY" | "HACIENDA" | "JULIET" | "ADONIS"
  start_time: string;  // "HH:MM"
  raw_name?: string;
};

export type RawSlot = {
  day: string;
  stage: string;
  start_time: string;
  name: string;        // as parsed from PDF (unmatched acts show up here too)
};

export type Act = {
  slug: string;
  name: string;
  url: string;
  bio: string;
  lowlands_genres: string[];
  subtitle: string;
  soundcloud: string;
  spotify: string;

  score: number;
  presence_score: number;
  vibe_score: number;
  vibe_reason: string;
  category: Category;

  reasons: string[];
  overridden: boolean;
  nts_links: NtsLink[];
  own_show: string | null;
  nts_genres: string[];
  nts_moods: string[];
  nts_description: string | null;
  episode_count: number;
  blurb: string;

  sets?: Set[];
};

export type Payload = {
  generated_at: string;
  timetable_updated_at?: string;
  acts: Act[];
  timetable?: RawSlot[];
  stats: {
    total: number;
    with_own_show: number;
    with_presence: number;
    with_vibe_50_plus: number;
    with_vibe_70_plus: number;
    with_timetable?: number;
  };
};
