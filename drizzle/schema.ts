import { int, mysqlEnum, mysqlTable, text, timestamp, varchar } from "drizzle-orm/mysql-core";

/**
 * Core user table backing auth flow.
 * Extend this file with additional tables as your product grows.
 * Columns use camelCase to match both database fields and generated types.
 */
export const users = mysqlTable("users", {
  /**
   * Surrogate primary key. Auto-incremented numeric value managed by the database.
   * Use this for relations between tables.
   */
  id: int("id").autoincrement().primaryKey(),
  /** Manus OAuth identifier (openId) returned from the OAuth callback. Unique per user. */
  openId: varchar("openId", { length: 64 }).notNull().unique(),
  name: text("name"),
  email: varchar("email", { length: 320 }),
  loginMethod: varchar("loginMethod", { length: 64 }),
  role: mysqlEnum("role", ["user", "admin"]).default("user").notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
  lastSignedIn: timestamp("lastSignedIn").defaultNow().notNull(),
});

export type User = typeof users.$inferSelect;
export type InsertUser = typeof users.$inferInsert;

// Silver Market Data Tables

export const comexFuturesData = mysqlTable("comex_futures_data", {
  id: int("id").autoincrement().primaryKey(),
  contractMonth: varchar("contract_month", { length: 20 }).notNull(), // e.g., "MAR2026"
  openInterest: int("open_interest").notNull(), // Number of contracts
  openInterestChange: int("open_interest_change"), // Daily change
  totalVolume: int("total_volume").notNull(), // Total trading volume
  settlementPrice: varchar("settlement_price", { length: 20 }).notNull(), // Price per ounce
  dataSource: varchar("data_source", { length: 100 }).notNull(), // e.g., "CME Group"
  recordedAt: timestamp("recorded_at").defaultNow().notNull(),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

export const slvInventoryData = mysqlTable("slv_inventory_data", {
  id: int("id").autoincrement().primaryKey(),
  tonnesInTrust: varchar("tonnes_in_trust", { length: 20 }).notNull(), // Tonnes
  ouncesInTrust: varchar("ounces_in_trust", { length: 30 }).notNull(), // Ounces
  netFlows: int("net_flows"), // Daily net flows in ounces
  sharePrice: varchar("share_price", { length: 20 }), // SLV share price
  dataSource: varchar("data_source", { length: 100 }).notNull(), // e.g., "iShares"
  recordedAt: timestamp("recorded_at").defaultNow().notNull(),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

export const comexInventoryData = mysqlTable("comex_inventory_data", {
  id: int("id").autoincrement().primaryKey(),
  registeredOunces: varchar("registered_ounces", { length: 30 }).notNull(), // Registered inventory
  eligibleOunces: varchar("eligible_ounces", { length: 30 }).notNull(), // Eligible inventory
  totalOunces: varchar("total_ounces", { length: 30 }).notNull(), // Total inventory
  dailyChange: varchar("daily_change", { length: 20 }), // Daily change in ounces
  dataSource: varchar("data_source", { length: 100 }).notNull(), // e.g., "CME Group"
  recordedAt: timestamp("recorded_at").defaultNow().notNull(),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

export const lbmaVaultData = mysqlTable("lbma_vault_data", {
  id: int("id").autoincrement().primaryKey(),
  totalTonnes: varchar("total_tonnes", { length: 20 }).notNull(), // Total silver in tonnes
  monthlyChange: varchar("monthly_change", { length: 20 }), // Monthly change percentage
  estimatedValue: varchar("estimated_value", { length: 30 }), // Estimated value in USD
  dataSource: varchar("data_source", { length: 100 }).notNull(), // e.g., "LBMA"
  recordedAt: timestamp("recorded_at").defaultNow().notNull(),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

export type ComexFuturesData = typeof comexFuturesData.$inferSelect;
export type InsertComexFuturesData = typeof comexFuturesData.$inferInsert;

export type SlvInventoryData = typeof slvInventoryData.$inferSelect;
export type InsertSlvInventoryData = typeof slvInventoryData.$inferInsert;

export type ComexInventoryData = typeof comexInventoryData.$inferSelect;
export type InsertComexInventoryData = typeof comexInventoryData.$inferInsert;

export type LbmaVaultData = typeof lbmaVaultData.$inferSelect;
export type InsertLbmaVaultData = typeof lbmaVaultData.$inferInsert;