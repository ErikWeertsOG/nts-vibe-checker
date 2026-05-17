export type NtsLink = { label: string; url: string };

export type Category = "RESIDENT" | "NTS-PRESENCE" | "NTS-VIBE" | "ADJACENT" | "OFF";

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
};

export type Payload = {
  generated_at: string;
  acts: Act[];
  stats: {
    total: number;
    with_own_show: number;
    with_presence: number;
    with_vibe_50_plus: number;
    with_vibe_70_plus: number;
  };
};
