import { eq } from "drizzle-orm";
import { drizzle } from "drizzle-orm/mysql2";
import { InsertUser, users, comexFuturesData, slvInventoryData, comexInventoryData, lbmaVaultData, InsertComexFuturesData, InsertSlvInventoryData, InsertComexInventoryData, InsertLbmaVaultData } from "../drizzle/schema";
import { ENV } from './_core/env';

let _db: ReturnType<typeof drizzle> | null = null;

// Lazily create the drizzle instance so local tooling can run without a DB.
export async function getDb() {
  if (!_db && process.env.DATABASE_URL) {
    try {
      _db = drizzle(process.env.DATABASE_URL);
    } catch (error) {
      console.warn("[Database] Failed to connect:", error);
      _db = null;
    }
  }
  return _db;
}

export async function upsertUser(user: InsertUser): Promise<void> {
  if (!user.openId) {
    throw new Error("User openId is required for upsert");
  }

  const db = await getDb();
  if (!db) {
    console.warn("[Database] Cannot upsert user: database not available");
    return;
  }

  try {
    const values: InsertUser = {
      openId: user.openId,
    };
    const updateSet: Record<string, unknown> = {};

    const textFields = ["name", "email", "loginMethod"] as const;
    type TextField = (typeof textFields)[number];

    const assignNullable = (field: TextField) => {
      const value = user[field];
      if (value === undefined) return;
      const normalized = value ?? null;
      values[field] = normalized;
      updateSet[field] = normalized;
    };

    textFields.forEach(assignNullable);

    if (user.lastSignedIn !== undefined) {
      values.lastSignedIn = user.lastSignedIn;
      updateSet.lastSignedIn = user.lastSignedIn;
    }
    if (user.role !== undefined) {
      values.role = user.role;
      updateSet.role = user.role;
    } else if (user.openId === ENV.ownerOpenId) {
      values.role = 'admin';
      updateSet.role = 'admin';
    }

    if (!values.lastSignedIn) {
      values.lastSignedIn = new Date();
    }

    if (Object.keys(updateSet).length === 0) {
      updateSet.lastSignedIn = new Date();
    }

    await db.insert(users).values(values).onDuplicateKeyUpdate({
      set: updateSet,
    });
  } catch (error) {
    console.error("[Database] Failed to upsert user:", error);
    throw error;
  }
}

export async function getUserByOpenId(openId: string) {
  const db = await getDb();
  if (!db) {
    console.warn("[Database] Cannot get user: database not available");
    return undefined;
  }

  const result = await db.select().from(users).where(eq(users.openId, openId)).limit(1);

  return result.length > 0 ? result[0] : undefined;
}

// Silver Market Data Queries

export async function getLatestComexFuturesData(contractMonth: string) {
  const db = await getDb();
  if (!db) return undefined;
  const result = await db
    .select()
    .from(comexFuturesData)
    .where(eq(comexFuturesData.contractMonth, contractMonth))
    .orderBy((t) => t.recordedAt)
    .limit(1);
  return result.length > 0 ? result[0] : undefined;
}

export async function getComexFuturesHistory(contractMonth: string, days: number = 30) {
  const db = await getDb();
  if (!db) return [];
  const cutoffDate = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
  return await db
    .select()
    .from(comexFuturesData)
    .where(eq(comexFuturesData.contractMonth, contractMonth))
    .orderBy((t) => t.recordedAt);
}

export async function getLatestSlvInventoryData() {
  const db = await getDb();
  if (!db) return undefined;
  const result = await db
    .select()
    .from(slvInventoryData)
    .orderBy((t) => t.recordedAt)
    .limit(1);
  return result.length > 0 ? result[0] : undefined;
}

export async function getSlvInventoryHistory(days: number = 30) {
  const db = await getDb();
  if (!db) return [];
  return await db
    .select()
    .from(slvInventoryData)
    .orderBy((t) => t.recordedAt);
}

export async function getLatestComexInventoryData() {
  const db = await getDb();
  if (!db) return undefined;
  const result = await db
    .select()
    .from(comexInventoryData)
    .orderBy((t) => t.recordedAt)
    .limit(1);
  return result.length > 0 ? result[0] : undefined;
}

export async function getComexInventoryHistory(days: number = 30) {
  const db = await getDb();
  if (!db) return [];
  return await db
    .select()
    .from(comexInventoryData)
    .orderBy((t) => t.recordedAt);
}

export async function getLatestLbmaVaultData() {
  const db = await getDb();
  if (!db) return undefined;
  const result = await db
    .select()
    .from(lbmaVaultData)
    .orderBy((t) => t.recordedAt)
    .limit(1);
  return result.length > 0 ? result[0] : undefined;
}

export async function getLbmaVaultHistory(months: number = 12) {
  const db = await getDb();
  if (!db) return [];
  return await db
    .select()
    .from(lbmaVaultData)
    .orderBy((t) => t.recordedAt);
}

export async function insertComexFuturesData(data: InsertComexFuturesData) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  await db.insert(comexFuturesData).values(data);
}

export async function insertSlvInventoryData(data: InsertSlvInventoryData) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  await db.insert(slvInventoryData).values(data);
}

export async function insertComexInventoryData(data: InsertComexInventoryData) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  await db.insert(comexInventoryData).values(data);
}

export async function insertLbmaVaultData(data: InsertLbmaVaultData) {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  await db.insert(lbmaVaultData).values(data);
}
