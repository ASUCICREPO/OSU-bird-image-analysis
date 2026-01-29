import { defineStorage } from '@aws-amplify/backend';

export const storage = defineStorage({
  name: 'birdProcessingBucket',
  access: (allow) => ({
    'public/uploads/*': [
      allow.guest.to(['read', 'write', 'delete'])
    ],
    'public/results/*': [
      allow.guest.to(['read'])
    ],
    'public/processed/*': [
      allow.guest.to(['read'])
    ],
    'uploads/*': [
      allow.guest.to(['read', 'write', 'delete'])
    ],
    'results/*': [
      allow.guest.to(['read'])
    ],
    'processed/*': [
      allow.guest.to(['read'])
    ]
  })
});