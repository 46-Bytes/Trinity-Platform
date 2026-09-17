import { buildEmbedUrl } from '@/lib/youtube';

interface YouTubePlayerProps {
  videoId: string;
  title: string;
}

/** Responsive 16:9 embedded YouTube player (privacy-enhanced nocookie domain). */
export function YouTubePlayer({ videoId, title }: YouTubePlayerProps) {
  return (
    <div className="relative w-full overflow-hidden rounded-lg bg-black aspect-video">
      <iframe
        className="absolute inset-0 h-full w-full"
        src={buildEmbedUrl(videoId)}
        title={title}
        loading="lazy"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        allowFullScreen
      />
    </div>
  );
}
