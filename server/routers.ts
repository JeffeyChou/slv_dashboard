import { COOKIE_NAME } from "@shared/const";
import { getSessionCookieOptions } from "./_core/cookies";
import { systemRouter } from "./_core/systemRouter";
import { publicProcedure, router } from "./_core/trpc";

export const appRouter = router({
    // if you need to use socket.io, read and register route in server/_core/index.ts, all api should start with '/api/' so that the gateway can route correctly
  system: systemRouter,
  auth: router({
    me: publicProcedure.query(opts => opts.ctx.user),
    logout: publicProcedure.mutation(({ ctx }) => {
      const cookieOptions = getSessionCookieOptions(ctx.req);
      ctx.res.clearCookie(COOKIE_NAME, { ...cookieOptions, maxAge: -1 });
      return {
        success: true,
      } as const;
    }),
  }),

  silverMarket: router({
    comexFutures: publicProcedure.query(async () => {
      const { getLatestComexFuturesData, getComexFuturesHistory } = await import('./db');
      const latest = await getLatestComexFuturesData('MAR2026');
      const history = await getComexFuturesHistory('MAR2026', 30);
      return { latest, history };
    }),
    slvInventory: publicProcedure.query(async () => {
      const { getLatestSlvInventoryData, getSlvInventoryHistory } = await import('./db');
      const latest = await getLatestSlvInventoryData();
      const history = await getSlvInventoryHistory(30);
      return { latest, history };
    }),
    comexInventory: publicProcedure.query(async () => {
      const { getLatestComexInventoryData, getComexInventoryHistory } = await import('./db');
      const latest = await getLatestComexInventoryData();
      const history = await getComexInventoryHistory(30);
      return { latest, history };
    }),
    lbmaVault: publicProcedure.query(async () => {
      const { getLatestLbmaVaultData, getLbmaVaultHistory } = await import('./db');
      const latest = await getLatestLbmaVaultData();
      const history = await getLbmaVaultHistory(12);
      return { latest, history };
    }),
  }),
});

export type AppRouter = typeof appRouter;
