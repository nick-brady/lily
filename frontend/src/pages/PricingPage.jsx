import { Link } from 'react-router-dom';
import PublicNav from '../components/PublicNav';

function Section({ heading, children }) {
  return (
    <section>
      <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100 mb-3">{heading}</h2>
      <div className="space-y-3 text-[15px] leading-relaxed text-gray-600 dark:text-gray-300">
        {children}
      </div>
    </section>
  );
}

export default function PricingPage() {
  return (
    <div className="min-h-screen bg-white dark:bg-gray-950">
      <PublicNav />

      <main className="max-w-3xl mx-auto px-6 pb-24 pt-6">
        <h1 className="text-3xl font-light text-gray-900 dark:text-white mb-3">
          What's free (and what isn't)
        </h1>
        <p className="text-gray-500 dark:text-gray-400 mb-10">
          The short version: everything live is free. You only ever pay for things you
          choose to keep.
        </p>

        <div className="space-y-8">
          <Section heading="While you're expecting, and while it's happening">
            <p>
              The page, the contraction timer, photos, videos, voice memos, comments,
              reactions, and as many family members as you want to invite. All of it is
              free, for everyone. There is no trial, no unlock, and nothing held back.
            </p>
            <p>
              We built this part to be free on purpose. Nobody should be thinking about
              a checkout page while a baby is being born.
            </p>
          </Section>

          <Section heading="The first year">
            <p>
              After the birth, the page stays live for a full year at no cost. Family
              can revisit it whenever they like, and you can keep adding to it.
            </p>
          </Section>

          <Section heading="After the first year">
            <p>
              Keeping the page live past the first year costs a small yearly amount.
              Around the first birthday we'll send you one gentle message with the
              choice. No countdowns, no pressure.
            </p>
            <p>
              Family members can also gift the page's permanence, for several years or
              forever, so the parents never have to think about it at all.
            </p>
            <p>
              And if you decide not to keep it live, nothing is deleted. The page is
              archived, and you can bring it back any time.
            </p>
          </Section>

          <Section heading="Keepsakes and prints">
            <p>
              Once the baby is here, we offer physical keepsakes made from your page:
              framed prints, photo books, mugs, announcement cards. Each is priced
              individually in the gift shop, and most are bought by family as gifts to
              the new parents. They are entirely optional. The page itself is the
              keepsake, and it doesn't cost anything to fill it.
            </p>
          </Section>

          <Section heading="Your memories are always yours">
            <p>
              Whether you ever pay us or not, you can download everything on your page,
              every photo, video, voice memo, comment, and contraction, as a single
              archive, free, at any time. We will never hold your memories hostage.
            </p>
          </Section>
        </div>

        <div className="mt-14 text-center">
          <Link to="/setup" className="btn-primary text-base px-8 py-4">
            Create your baby's page →
          </Link>
          <p className="mt-4 text-sm text-gray-400">Free for your whole family. No app to download.</p>
        </div>
      </main>

      <footer className="text-center py-8 text-gray-400 text-sm border-t border-gray-100 dark:border-gray-800 space-x-4">
        <Link to="/privacy" className="hover:text-primary-600 dark:hover:text-primary-400">Privacy Policy</Link>
        <Link to="/terms" className="hover:text-primary-600 dark:hover:text-primary-400">Terms of Service</Link>
      </footer>
    </div>
  );
}
