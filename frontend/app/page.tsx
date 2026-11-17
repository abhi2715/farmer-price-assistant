import Link from "next/link";
import Reveal from "@/components/Reveal";

const WORDS = [
  { w: "What", d: "Which crop to sell now, and which to hold." },
  { w: "Where", d: "The mandi that pays the most after transport and fees." },
  { w: "When", d: "The day the price peaks — before your harvest spoils." },
  { w: "Who", d: "A direct buyer who pays more than the mandi." },
];

const STEPS = [
  { n: "01", t: "Pick your crop", d: "One tap. Or just say it — in Kannada, Hindi or English." },
  { n: "02", t: "Say how much", d: "Quintals, with big buttons made for thumbs." },
  { n: "03", t: "Get your best sale", d: "Mandi, date and the rupees you take home — with the reasons, in plain words." },
];

export default function Landing() {
  return (
    <div className="overflow-x-hidden bg-white text-soil-900">
      <nav className="fixed inset-x-0 top-0 z-30 border-b border-black/5 bg-white/75 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3">
          <a href="#top" className="flex items-center gap-2 font-semibold tracking-tight">
            <img src="/icons/icon.svg" alt="" width={26} height={26} /> AgriRoute
          </a>
          <div className="flex items-center gap-5 text-sm">
            <a href="#how" className="hidden text-soil-500 hover:text-soil-900 sm:inline">How it works</a>
            <a href="#market" className="hidden text-soil-500 hover:text-soil-900 sm:inline">Marketplace</a>
            <Link href="/login/" className="rounded-full bg-soil-900 px-4 py-1.5 font-medium text-white">Open app</Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section id="top" className="relative flex min-h-[100svh] flex-col items-center justify-center px-5 pt-20 text-center">
        <div aria-hidden className="pointer-events-none absolute inset-x-0 top-1/3 -z-0 mx-auto h-[40vh] max-w-4xl rounded-full bg-leaf-100/60 blur-3xl" />
        <p className="relative animate-rise text-sm font-semibold uppercase tracking-[0.25em] text-leaf-700">ಕನ್ನಡ · हिन्दी · English</p>
        <h1 className="relative mt-5 animate-rise text-[clamp(3.25rem,13vw,10rem)] font-bold leading-[0.92] tracking-[-0.045em] [animation-delay:120ms]">
          Sell smarter.
          <br />
          <span className="text-gradient">Earn more.</span>
        </h1>
        <p className="relative mx-auto mt-8 max-w-xl animate-rise text-[clamp(1.1rem,2.6vw,1.5rem)] leading-snug text-soil-500 [animation-delay:260ms]">
          AgriRoute tells every farmer what to sell, where, when — and to whom — for the best net profit.
        </p>
        <div className="relative mt-10 flex animate-rise flex-col gap-3 sm:flex-row [animation-delay:380ms]">
          <Link href="/login/?role=farmer" className="rounded-full bg-leaf-600 px-8 py-4 text-lg font-semibold text-white shadow-lg shadow-leaf-600/25 transition hover:bg-leaf-700">
            I&apos;m a farmer
          </Link>
          <Link href="/login/?role=buyer" className="rounded-full px-8 py-4 text-lg font-semibold text-leaf-700 ring-1 ring-leaf-600/30 transition hover:bg-leaf-50">
            I&apos;m a buyer →
          </Link>
        </div>
        <a href="#words" aria-label="Scroll" className="absolute bottom-8 animate-fade text-soil-400 [animation-delay:900ms]">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M6 9l6 6 6-6" /></svg>
        </a>
      </section>

      {/* Four words */}
      <section id="words" className="mx-auto max-w-6xl px-5 py-24 sm:py-36">
        {WORDS.map((x, i) => (
          <Reveal key={x.w} delay={i * 60} className="border-t border-soil-100 py-10 sm:py-14">
            <div className="grid items-baseline gap-3 sm:grid-cols-[1.2fr_1fr]">
              <h2 className="text-[clamp(3.5rem,12vw,8.5rem)] font-bold leading-none tracking-[-0.05em]">{x.w}.</h2>
              <p className="text-xl leading-snug text-soil-500 sm:text-2xl">{x.d}</p>
            </div>
          </Reveal>
        ))}
      </section>

      {/* Big number */}
      <section className="bg-soil-900 px-5 py-28 text-center text-white sm:py-40">
        <Reveal>
          <p className="text-lg text-soil-400">For tomatoes, onions and potatoes, farmers get about a third of what consumers pay (RBI, 2024).</p>
          <p className="mt-6 text-[clamp(3.5rem,13vw,10rem)] font-bold leading-none tracking-[-0.05em]">
            <span className="text-gradient">Every mandi.</span>
            <br />
            Every day.
          </p>
          <p className="mx-auto mt-6 max-w-xl text-xl text-soil-400">
            For each sale we compare nearby mandis over the next two weeks — price, transport, fees and spoilage — and pick what leaves the most in your pocket.
          </p>
        </Reveal>
      </section>

      {/* How */}
      <section id="how" className="mx-auto max-w-6xl px-5 py-24 sm:py-36">
        <Reveal>
          <h2 className="max-w-3xl text-[clamp(2.5rem,7vw,5.5rem)] font-bold leading-[0.95] tracking-[-0.04em]">
            Three taps. <span className="text-soil-400">That&apos;s it.</span>
          </h2>
        </Reveal>
        <div className="mt-16 grid gap-6 sm:grid-cols-3">
          {STEPS.map((s, i) => (
            <Reveal key={s.n} delay={i * 120}>
              <div className="h-full rounded-[2rem] bg-soil-50 p-8">
                <div className="text-sm font-semibold text-leaf-600">{s.n}</div>
                <h3 className="mt-6 text-3xl font-bold tracking-tight">{s.t}</h3>
                <p className="mt-3 text-lg leading-snug text-soil-500">{s.d}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* Forecast + explain */}
      <section className="mx-auto max-w-6xl px-5 pb-24 sm:pb-36">
        <div className="grid gap-6 lg:grid-cols-2">
          <Reveal>
            <div className="flex h-full flex-col justify-between rounded-[2rem] bg-leaf-50 p-8 sm:p-12">
              <h3 className="text-4xl font-bold tracking-tight sm:text-5xl">Prices, 30 days ahead.</h3>
              <p className="mt-6 text-lg text-soil-700">
                Forecasts for every crop at every mandi, with honest ranges. Built from mandi prices, arrivals, weather, festivals and MSP — and checked against the past before we trust them.
              </p>
            </div>
          </Reveal>
          <Reveal delay={120}>
            <div className="flex h-full flex-col justify-between rounded-[2rem] bg-amber-50 p-8 sm:p-12">
              <h3 className="text-4xl font-bold tracking-tight sm:text-5xl">Reasons, not riddles.</h3>
              <p className="mt-6 text-lg text-soil-700">
                “Dasara is coming — demand rises before festivals.” Every recommendation explains itself in simple words, and reads itself aloud.
              </p>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Marketplace */}
      <section id="market" className="bg-soil-50 px-5 py-24 sm:py-36">
        <div className="mx-auto max-w-6xl text-center">
          <Reveal>
            <h2 className="text-[clamp(2.5rem,8vw,6.5rem)] font-bold leading-[0.95] tracking-[-0.045em]">
              Buyers, <span className="text-gradient">matched.</span>
            </h2>
            <p className="mx-auto mt-8 max-w-2xl text-xl text-soil-500">
              Post your lot. We match it to traders, processors and retailers by crop, grade, quantity, distance and price — and split the difference fairly.
            </p>
            <Link href="/login/?role=buyer" className="mt-10 inline-block rounded-full bg-soil-900 px-8 py-4 text-lg font-semibold text-white">
              Source directly from farms
            </Link>
          </Reveal>
        </div>
      </section>

      {/* Built for */}
      <section className="mx-auto max-w-6xl px-5 py-24 text-center sm:py-32">
        <Reveal>
          <div className="grid gap-10 sm:grid-cols-3">
            {[["Works offline", "Saved prices and queued posts when the network drops."], ["Tiny & fast", "Loads on 2G and low-end Android phones."], ["Speaks your language", "Voice in and out, in ಕನ್ನಡ, हिन्दी and English."]].map(([a, b]) => (
              <div key={a}>
                <div className="text-2xl font-bold tracking-tight">{a}</div>
                <p className="mt-2 text-soil-500">{b}</p>
              </div>
            ))}
          </div>
        </Reveal>
      </section>

      <footer className="border-t border-soil-100 px-5 py-10 text-center text-sm text-soil-400">
        AgriRoute · Farm-to-market, optimised. · <Link href="/login/" className="underline">Open the app</Link>
      </footer>
    </div>
  );
}
