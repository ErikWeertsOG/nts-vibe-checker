export type NtsLink = { label: string; url: string };

export type Act = {
  slug: string;
  name: string;
  url: string;
  score: number;
  reasons: string[];
  nts_links: NtsLink[];
  own_show: string | null;
  genres: string[];
  moods: string[];
  nts_description: string | null;
  episode_count: number;
  blurb: string;
};

export type Payload = {
  generated_at: string;
  acts: Act[];
  stats: { total: number; with_own_show: number; with_any_signal: number };
};
