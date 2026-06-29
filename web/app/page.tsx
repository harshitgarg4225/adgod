"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getUser } from "@/lib/api";

export default function Index() {
  const router = useRouter();
  useEffect(() => {
    router.replace(getUser() ? "/dashboard" : "/login");
  }, [router]);
  return null;
}
