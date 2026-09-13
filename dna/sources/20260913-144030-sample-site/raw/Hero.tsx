export function Hero() {
  return (
    <section className="section flex flex-col gap-4 py-12 px-6 md:px-8 lg:px-12">
      <h1 className="text-5xl font-bold tracking-tight text-slate-900">
        把想法變成看得見的東西
      </h1>
      <p className="text-base leading-relaxed text-slate-500 max-w-prose">
        我們幫你把粗略的構想，做成能直接上線的介面。
      </p>
      <div className="cluster flex gap-2 items-center">
        <a className="btn-primary rounded-xl px-6 py-3 transition duration-200" href="/start">
          開始使用
        </a>
        <a className="btn-ghost rounded-xl px-6 py-3" href="/docs">
          看文件
        </a>
      </div>
    </section>
  );
}
