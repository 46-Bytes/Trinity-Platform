import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchCategoriesWithVideos } from '@/store/slices/helpReducer';
import { YouTubePlayer } from '@/components/help/YouTubePlayer';
import { Loader2, Settings, PlayCircle } from 'lucide-react';
import { toast } from 'sonner';

export default function HelpPage() {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { categories, isLoading, error } = useAppSelector((state) => state.help);

  const isAdmin = user?.role === 'super_admin' || user?.role === 'admin';

  useEffect(() => {
    dispatch(fetchCategoriesWithVideos());
  }, [dispatch]);

  useEffect(() => {
    if (error) toast.error(error);
  }, [error]);

  const hasContent = categories.some((c) => c.videos.length > 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex-shrink-0 w-11 h-11 rounded-xl bg-gradient-to-br from-accent to-accent/70 text-accent-foreground flex items-center justify-center shadow-sm">
            <PlayCircle className="w-6 h-6" />
          </div>
          <h1 className="font-heading text-2xl font-bold text-foreground">Help &amp; User Guide</h1>
        </div>
        {isAdmin && (
          <button className="btn-primary" onClick={() => navigate('/dashboard/help/manage')}>
            <Settings className="w-4 h-4" />
            Manage videos
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 animate-spin text-accent" />
          <span className="ml-2 text-muted-foreground">Loading videos...</span>
        </div>
      ) : !hasContent ? (
        <div className="card-trinity p-12 text-center">
          <div className="w-14 h-14 rounded-2xl bg-accent/10 text-accent flex items-center justify-center mx-auto">
            <PlayCircle className="w-7 h-7" />
          </div>
          <p className="text-foreground font-medium mt-4">No help videos yet</p>
          <p className="text-sm text-muted-foreground mt-1">
            {isAdmin
              ? 'Use “Manage videos” to add your first category and video.'
              : 'Check back soon — training videos will appear here.'}
          </p>
        </div>
      ) : (
        <div className="space-y-10">
          {categories
            .filter((category) => category.videos.length > 0)
            .map((category, catIndex) => (
              <section
                key={category.id}
                className="space-y-4 animate-fade-in"
                style={{ animationDelay: `${catIndex * 60}ms` }}
              >
                <div className="flex items-center gap-3 border-b border-border/60 pb-3">
                  <div className="w-1.5 h-9 rounded-full bg-gradient-to-b from-accent to-accent/60" />
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h2 className="font-heading text-xl font-semibold text-foreground">{category.name}</h2>
                      <span className="status-badge bg-accent/10 text-accent">
                        {category.videos.length} {category.videos.length === 1 ? 'video' : 'videos'}
                      </span>
                    </div>
                    {category.description && (
                      <p className="text-muted-foreground text-sm mt-0.5">{category.description}</p>
                    )}
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                  {category.videos.map((video) => (
                    <div key={video.id} className="card-trinity p-3 space-y-3 group">
                      <div className="overflow-hidden rounded-lg">
                        <YouTubePlayer videoId={video.youtube_video_id} title={video.title} />
                      </div>
                      <div className="px-1 pb-1">
                        <h3 className="font-medium text-foreground group-hover:text-accent transition-colors">
                          {video.title}
                        </h3>
                        {video.description && (
                          <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{video.description}</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            ))}
        </div>
      )}
    </div>
  );
}
