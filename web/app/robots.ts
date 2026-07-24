import type { MetadataRoute } from "next";

// Public marketing/legal pages are indexable; everything behind login is not.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/terms", "/privacy", "/refunds", "/contact", "/login"],
        disallow: [
          "/dashboard",
          "/leads",
          "/reports",
          "/billing",
          "/settings",
          "/onboarding",
          "/admin",
          "/partner",
          "/wallet",
          "/ads",
          "/bookings",
          "/notifications",
        ],
      },
    ],
  };
}
