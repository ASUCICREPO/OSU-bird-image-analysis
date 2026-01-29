import { defineAuth } from '@aws-amplify/backend';

/**
 * Define authentication configuration
 * Supports email-based sign up and sign in
 */
export const auth = defineAuth({
  loginWith: {
    email: true
  },
  userAttributes: {
    email: {
      required: true,
      mutable: true
    },
    givenName: {
      required: false,
      mutable: true
    },
    familyName: {
      required: false,
      mutable: true
    }
  }
});