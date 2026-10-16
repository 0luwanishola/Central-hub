import type { NewsItem } from "../../types";
import { Icon } from "../../ui/Icon";

interface NewsItemProps {
  item: NewsItem;
}

export function NewsItemComponent({ item }: NewsItemProps) {
  return (
    <article className="news-row">
      <a
        href={item.url}
        target="_blank"
        rel="noopener noreferrer"
        className="news-link"
        aria-label={`Read "${item.title}" on ${item.source}`}
      >
        <h3 className="news-title">{item.title}</h3>
        <div className="news-meta">
          <span className="news-source">{item.source}</span>
          <time className="news-time" dateTime={item.publishedAt}>
            {formatRelativeTime(item.publishedAt)}
          </time>
        </div>
      </a>
      <Icon name="external" className="news-external" aria-hidden="true" />
    </article>
  );
}

function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  if (isNaN(date.getTime())) return "Unknown time";

  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 30) return "Just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHour < 24) return `${diffHour}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;

  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}