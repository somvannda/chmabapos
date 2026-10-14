export function meta() {
  return [
    { title: "Chmaba Storefront" },
    { name: "description", content: "Shop directly from local stores on Chmaba." },
    { name: "robots", content: "noindex" },
  ];
}

// The storefront host root is not a directory yet. The public directory lands in
// phase 7; until then this explains the host rather than 404ing.
export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-[560px] flex-col items-center justify-center px-6 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-soft text-brand">
        <span className="text-lg font-black">C</span>
      </span>
      <h1 className="mt-5 text-2xl font-extrabold tracking-[-.04em]">Chmaba storefronts</h1>
      <p className="mt-2 text-sm leading-6 text-muted">
        Open a store with the link its owner shared, in the form{" "}
        <code className="rounded bg-surface-sunken px-1.5 py-0.5 text-xs">/business-name/store-name</code>.
      </p>
    </main>
  );
}
