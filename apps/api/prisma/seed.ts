import { PrismaClient, OddsProviderType } from '@prisma/client';

const prisma = new PrismaClient();

const ONTARIO_BOOKS = [
  { name: 'BetMGM Ontario', code: 'betmgm_on', region: 'ON', isOntarioLicensed: true },
  { name: 'BetRivers Ontario', code: 'betrivers_on', region: 'ON', isOntarioLicensed: true },
  { name: 'DraftKings Ontario', code: 'draftkings_on', region: 'ON', isOntarioLicensed: true },
  { name: 'FanDuel Ontario', code: 'fanduel_on', region: 'ON', isOntarioLicensed: true },
  { name: 'PointsBet Ontario', code: 'pointsbet_on', region: 'ON', isOntarioLicensed: true },
  { name: 'theScore Bet', code: 'thescore_on', region: 'ON', isOntarioLicensed: true },
  { name: 'Caesars Sportsbook Ontario', code: 'caesars_on', region: 'ON', isOntarioLicensed: true },
  { name: 'Sports Interaction', code: 'sportsinteraction_on', region: 'ON', isOntarioLicensed: true },
];

const GLOBAL_BOOKS = [
  { name: 'Pinnacle', code: 'pinnacle', region: 'INT', isOntarioLicensed: false },
  { name: 'Bovada', code: 'bovada', region: 'US', isOntarioLicensed: false },
  { name: 'Bet365', code: 'bet365', region: 'INT', isOntarioLicensed: false },
  { name: 'William Hill', code: 'williamhill', region: 'UK', isOntarioLicensed: false },
];

/** The Odds API bookmaker keys → internal sportsbook codes */
const THE_ODDS_API_MAPPINGS: Record<string, string> = {
  draftkings: 'draftkings_on',
  fanduel: 'fanduel_on',
  betmgm: 'betmgm_on',
  betrivers: 'betrivers_on',
  pointsbet: 'pointsbet_on',
  williamhill_us: 'williamhill',
  bovada: 'bovada',
  bet365: 'bet365',
  pinnacle: 'pinnacle',
};

async function main() {
  for (const book of [...ONTARIO_BOOKS, ...GLOBAL_BOOKS]) {
    await prisma.sportsbook.upsert({
      where: { code: book.code },
      create: book,
      update: { name: book.name, isOntarioLicensed: book.isOntarioLicensed },
    });
  }

  const theOddsApi = await prisma.oddsProvider.upsert({
    where: { code: 'the_odds_api' },
    create: {
      name: 'The Odds API',
      code: 'the_odds_api',
      type: OddsProviderType.aggregator,
      baseUrl: process.env.THE_ODDS_API_BASE_URL ?? 'https://api.the-odds-api.com/v4',
      isEnabled: true,
    },
    update: {},
  });

  const books = await prisma.sportsbook.findMany();
  const bookByCode = Object.fromEntries(books.map((b) => [b.code, b]));

  for (const [providerCode, internalCode] of Object.entries(THE_ODDS_API_MAPPINGS)) {
    const sb = bookByCode[internalCode];
    if (!sb) continue;
    await prisma.sportsbookProviderMapping.upsert({
      where: {
        oddsProviderId_providerBookCode: {
          oddsProviderId: theOddsApi.id,
          providerBookCode: providerCode,
        },
      },
      create: {
        sportsbookId: sb.id,
        oddsProviderId: theOddsApi.id,
        providerBookCode: providerCode,
      },
      update: { sportsbookId: sb.id },
    });
  }

  const sports = [
    { slug: 'basketball', name: 'Basketball', leagues: [{ slug: 'nba', name: 'NBA' }] },
    { slug: 'americanfootball', name: 'American Football', leagues: [{ slug: 'nfl', name: 'NFL' }] },
    { slug: 'soccer', name: 'Soccer', leagues: [{ slug: 'epl', name: 'English Premier League' }] },
    { slug: 'icehockey', name: 'Ice Hockey', leagues: [{ slug: 'nhl', name: 'NHL' }] },
  ];

  for (const s of sports) {
    const sport = await prisma.sport.upsert({
      where: { slug: s.slug },
      create: { name: s.name, slug: s.slug },
      update: { name: s.name },
    });
    for (const l of s.leagues) {
      await prisma.league.upsert({
        where: { sportId_slug: { sportId: sport.id, slug: l.slug } },
        create: { sportId: sport.id, name: l.name, slug: l.slug },
        update: { name: l.name },
      });
    }
  }

  console.log('Seed complete: sportsbooks, provider mappings, sports/leagues');
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
