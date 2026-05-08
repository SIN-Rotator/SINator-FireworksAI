const adjectives = [
  'elron', 'dark', 'swift', 'iron', 'silver', 'golden', 'black', 'red',
  'blue', 'storm', 'fire', 'ice', 'shadow', 'bright', 'wild', 'stone',
  'thunder', 'ghost', 'steel', 'neon', 'cyber', 'alpha', 'omega', 'nova',
  'solar', 'lunar', 'astro', 'turbo', 'hyper', 'ultra', 'mega', 'super',
];

const nouns = [
  'vader', 'runner', 'hawk', 'wolf', 'fox', 'bear', 'eagle', 'tiger',
  'lion', 'shark', 'blade', 'storm', 'rider', 'hunter', 'seeker', 'knight',
  'wizard', 'ranger', 'pilot', 'scout', 'agent', 'cipher', 'nexus', 'apex',
  'viper', 'cobra', 'falcon', 'raven', 'phoenix', 'dragon', 'titan', 'zeus',
];

function generateAliasName() {
  const adj = adjectives[Math.floor(Math.random() * adjectives.length)];
  const noun = nouns[Math.floor(Math.random() * nouns.length)];
  return `${adj}-${noun}`;
}

function splitAliasToName(alias) {
  const parts = alias.split('-');
  const firstName = parts[0].charAt(0).toUpperCase() + parts[0].slice(1);
  const lastName = parts[1]
    ? parts[1].charAt(0).toUpperCase() + parts[1].slice(1)
    : 'User';
  return { firstName, lastName };
}

module.exports = { generateAliasName, splitAliasToName };