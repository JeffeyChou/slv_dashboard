CREATE TABLE `comex_futures_data` (
	`id` int AUTO_INCREMENT NOT NULL,
	`contract_month` varchar(20) NOT NULL,
	`open_interest` int NOT NULL,
	`open_interest_change` int,
	`total_volume` int NOT NULL,
	`settlement_price` varchar(20) NOT NULL,
	`data_source` varchar(100) NOT NULL,
	`recorded_at` timestamp NOT NULL DEFAULT (now()),
	`created_at` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `comex_futures_data_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `comex_inventory_data` (
	`id` int AUTO_INCREMENT NOT NULL,
	`registered_ounces` varchar(30) NOT NULL,
	`eligible_ounces` varchar(30) NOT NULL,
	`total_ounces` varchar(30) NOT NULL,
	`daily_change` varchar(20),
	`data_source` varchar(100) NOT NULL,
	`recorded_at` timestamp NOT NULL DEFAULT (now()),
	`created_at` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `comex_inventory_data_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `lbma_vault_data` (
	`id` int AUTO_INCREMENT NOT NULL,
	`total_tonnes` varchar(20) NOT NULL,
	`monthly_change` varchar(20),
	`estimated_value` varchar(30),
	`data_source` varchar(100) NOT NULL,
	`recorded_at` timestamp NOT NULL DEFAULT (now()),
	`created_at` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `lbma_vault_data_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `slv_inventory_data` (
	`id` int AUTO_INCREMENT NOT NULL,
	`tonnes_in_trust` varchar(20) NOT NULL,
	`ounces_in_trust` varchar(30) NOT NULL,
	`net_flows` int,
	`share_price` varchar(20),
	`data_source` varchar(100) NOT NULL,
	`recorded_at` timestamp NOT NULL DEFAULT (now()),
	`created_at` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `slv_inventory_data_id` PRIMARY KEY(`id`)
);
