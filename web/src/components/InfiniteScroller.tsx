import { useEffect, useRef } from "react";

interface Props {
  /** 触底时调用，用于从牌堆再发一批题。 */
  onReachEnd: () => void;
  /** 本轮已发完时停止观察。 */
  disabled: boolean;
}

/**
 * 用 IntersectionObserver 盯住列表底部的哨兵元素。
 * 相比监听 scroll 事件，它不需要节流，也不会在移动端因惯性滚动丢触发。
 */
export function InfiniteScroller({ onReachEnd, disabled }: Props) {
  const sentinel = useRef<HTMLDivElement>(null);
  const cb = useRef(onReachEnd);
  cb.current = onReachEnd;

  useEffect(() => {
    if (disabled) return;
    const node = sentinel.current;
    if (!node) return;

    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) cb.current();
      },
      { rootMargin: "400px 0px" }, // 提前 400px 预加载，滚动更顺
    );
    io.observe(node);
    return () => io.disconnect();
  }, [disabled]);

  return <div ref={sentinel} className="sentinel" aria-hidden="true" />;
}
