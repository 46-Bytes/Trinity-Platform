export interface HelpVideo {
  id: string;
  category_id: string;
  youtube_video_id: string;
  title: string;
  description?: string | null;
  position: number;
  embed_url: string;
  created_at: string;
  updated_at: string;
}

export interface HelpVideoCategory {
  id: string;
  name: string;
  description?: string | null;
  position: number;
  created_at: string;
  updated_at: string;
}

export interface CategoryWithVideos extends HelpVideoCategory {
  videos: HelpVideo[];
}
