// Single source for brand, contact and legal details used across the site.
export const site = {
  name: "déjà view",
  title: "déjà view: root cause suggestions for on-call engineers",
  description:
    "Describe a production issue in plain words and get likely root causes and fixes, grounded in the closest of 2,856 past production incidents.",
  url: process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  analyzerUrl: (process.env.NEXT_PUBLIC_ANALYZER_URL ?? "http://127.0.0.1:5173").replace(/\/+$/, ""),
  apiUrl: (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/+$/, ""),
  repoUrl: "https://github.com/Navjot-kr-Singh/RCA",
  legal: {
    owner: "Navjot Kumar Singh",
    email: "navjotkumarsingh81@gmail.com",
    // Not provided yet. Both must be filled in before launch; the legal pages
    // show a visible "to be added" marker while they are null.
    address: null as string | null,
    jurisdiction: null as string | null,
    lastUpdated: "2026-10-10",
  },
};
