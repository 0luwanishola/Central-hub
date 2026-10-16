import { useLatestNews } from "./useNews";
import { NewsItemComponent } from "./NewsItem";
import { Icon } from "../../ui/Icon";

interface LatestNewsProps {
  limit?: number;
}

export function LatestNews({ limit = 5 }: LatestNewsProps) {
  const { data, isLoading, isError, refetch } = useLatestNews(limit);

  if (isLoading) {
    return (
      <section className="news-section" aria-labelledby="news-heading" aria-busy="true">
        <div className="section-heading news-section-heading">
          <div>
            <span className="eyebrow">Latest</span>
            <h2 id="news-heading">Headlines</h2>
          </div>
        </div>
        <div className="news-list" role="list" aria-label="Loading headlines">
          {Array.from({ length: limit }).map((_, i) => (
            <div key={i} className="news-row skeleton" aria-hidden="true">
              <div className="news-skeleton-title" />
              <div className="news-skeleton-meta" />
            </div>
          ))}
        </div>
      </section>
    );
  }

  if (isError) {
    return (
      <section className="news-section" aria-labelledby="news-heading">
        <div className="section-heading news-section-heading">
          <div>
            <span className="eyebrow">Latest</span>
            <h2 id="news-heading">Headlines</h2>
          </div>
        </div>
        <div className="news-error" role="alert">
          <p>Couldn't load headlines.</p>
          <button className="button button-secondary" type="button" onClick={() => refetch()}>
            <Icon name="refresh" /> Retry
          </button>
        </div>
      </section>
    );
  }

  const items = data?.items ?? [];
  if (items.length === 0) {
    return (
      <section className="news-section" aria-labelledby="news-heading">
        <div className="section-heading news-section-heading">
          <div>
            <span className="eyebrow">Latest</span>
            <h2 id="news-heading">Headlines</h2>
          </div>
        </div>
        <div className="news-empty" role="status">
          <p>No headlines available right now.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="news-section" aria-labelledby="news-heading">
      <div className="section-heading news-section-heading">
        <div>
          <span className="eyebrow">Latest</span>
          <h2 id="news-heading">Headlines</h2>
        </div>
      </div>
      {data?.stale && (
        <p className="news-stale" role="status">
          Live refresh failed — showing the most recent saved headlines.
        </p>
      )}
      <div className="news-list" role="list" aria-label="Latest headlines">
        {items.map((item) => (
          <NewsItemComponent key={item.id} item={item} />
        ))}
      </div>
    </section>
  );
}