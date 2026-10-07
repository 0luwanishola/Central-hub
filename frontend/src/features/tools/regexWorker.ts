type RegexRequest = { pattern: string; flags: string; sample: string };
type RegexResponse = { matches?: string[]; error?: string; truncated?: boolean };

const workerScope = self as unknown as {
  onmessage: ((event: MessageEvent<RegexRequest>) => void) | null;
  postMessage: (message: RegexResponse) => void;
};

workerScope.onmessage = ({ data }) => {
  try {
    const expression = new RegExp(data.pattern, data.flags);
    const matches: string[] = [];
    let outputLength = 0;
    let truncated = false;

    for (const match of data.sample.matchAll(expression)) {
      const rendered = `${match[0]}  ·  index ${match.index ?? 0}`;
      if (matches.length >= 500 || outputLength + rendered.length > 50_000) {
        truncated = true;
        break;
      }
      matches.push(rendered);
      outputLength += rendered.length;
    }

    workerScope.postMessage({ matches, truncated });
  } catch (reason) {
    workerScope.postMessage({ error: reason instanceof Error ? reason.message : "Invalid regular expression." });
  }
};
