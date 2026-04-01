-- MySQL dump 10.13  Distrib 8.0.45, for Win64 (x86_64)
--
-- Host: user-trial-database.cblvpmltfuj8.eu-west-1.rds.amazonaws.com    Database: user_trial_system_v1
-- ------------------------------------------------------
-- Server version	8.0.44

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `approval_actions`
--

DROP TABLE IF EXISTS `approval_actions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `approval_actions` (
  `ActionID` int NOT NULL AUTO_INCREMENT,
  `ApprovalType` enum('product_trial','bonus_survey') NOT NULL,
  `ApprovalID` varchar(64) NOT NULL,
  `ActionType` enum('approve','request_info','info_provided','request_changes','change_countered','change_accepted','withdraw_request','decline') NOT NULL,
  `ReasonCategory` enum('incomplete_info','scope_unclear','timing_conflict','resource_constraints','process_violation','quality_concerns','other') DEFAULT NULL,
  `ReasonText` text,
  `AssignedUTLeadID` varchar(64) DEFAULT NULL,
  `ActionByUserID` varchar(64) NOT NULL,
  `CreatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ActionID`)
) ENGINE=InnoDB AUTO_INCREMENT=38 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `approval_actions`
--

LOCK TABLES `approval_actions` WRITE;
/*!40000 ALTER TABLE `approval_actions` DISABLE KEYS */;
INSERT INTO `approval_actions` VALUES (1,'product_trial','16','decline',NULL,'Inappropriate reason for a trial. get it together!',NULL,'userid_4fec82c7eea61','2026-02-06 08:13:33'),(2,'product_trial','15','decline',NULL,'Inappropriate reason for a trial. get it together!',NULL,'userid_4fec82c7eea61','2026-02-06 08:15:56'),(3,'product_trial','10','decline',NULL,'Firmware not mature enough for Trial.',NULL,'userid_4fec82c7eea61','2026-02-06 08:24:11'),(4,'product_trial','13','request_info',NULL,'Need more clarity on why the dates conflict',NULL,'userid_4fec82c7eea61','2026-02-06 11:49:38'),(5,'product_trial','13','request_info',NULL,'Needs more cowbell',NULL,'userid_4fec82c7eea61','2026-02-06 11:52:14'),(6,'product_trial','12','request_changes',NULL,'Please revise the ship date and clarify Gate X timing.',NULL,'userid_4fec82c7eea61','2026-02-06 12:05:23'),(7,'product_trial','14','request_changes',NULL,'Please revise the ship date and clarify Gate X timing.',NULL,'userid_4fec82c7eea61','2026-02-06 12:09:18'),(8,'product_trial','3','approve',NULL,NULL,'userid_d593d38eed2a1','userid_4fec82c7eea61','2026-02-08 06:55:33'),(9,'product_trial','13','request_info',NULL,'We have added more cowbell.',NULL,'userid_4fec82c7eea61','2026-02-09 03:21:52'),(10,'product_trial','17','request_info',NULL,'I need to know where you got that dress.',NULL,'userid_4fec82c7eea61','2026-02-09 03:38:18'),(11,'product_trial','18','request_info',NULL,'What is the air speed velocity of a laden swallow?',NULL,'userid_4fec82c7eea61','2026-02-09 04:09:49'),(12,'product_trial','18','info_provided',NULL,'African or European?',NULL,'userid_4fec82c7eea61','2026-02-09 05:16:38'),(13,'product_trial','14','change_accepted',NULL,NULL,NULL,'userid_4fec82c7eea61','2026-02-09 05:41:59'),(14,'product_trial','14','approve',NULL,NULL,'userid_4fec82c7eea61','userid_4fec82c7eea61','2026-02-09 07:05:40'),(15,'product_trial','18','approve',NULL,NULL,'userid_4fec82c7eea61','userid_4fec82c7eea61','2026-02-09 07:17:10'),(16,'product_trial','17','info_provided',NULL,'\"You\'re straight, you\'re engaged, tomorrow is your girl\'s birthday, and you have no taste in women\'s fashion... What if she was an asset: You told her four lies that now have to be true.\"',NULL,'userid_4fec82c7eea61','2026-02-09 09:21:56'),(17,'product_trial','17','request_info',NULL,'Explain why the sky is blue',NULL,'userid_4fec82c7eea61','2026-02-09 09:33:37'),(18,'product_trial','17','info_provided',NULL,'refraction of light against the atmosphere of the earth',NULL,'userid_4fec82c7eea61','2026-02-09 09:35:34'),(19,'product_trial','17','approve',NULL,NULL,'userid_4fec82c7eea61','userid_4fec82c7eea61','2026-02-09 09:36:33'),(20,'bonus_survey','4','approve',NULL,NULL,'userid_4fec82c7eea61','userid_4fec82c7eea61','2026-02-11 02:13:33'),(21,'bonus_survey','4','approve',NULL,NULL,'userid_4fec82c7eea61','userid_4fec82c7eea61','2026-02-11 02:15:18'),(22,'bonus_survey','4','approve',NULL,NULL,'userid_4fec82c7eea61','userid_4fec82c7eea61','2026-02-11 02:35:34'),(23,'product_trial','11','approve',NULL,NULL,'userid_4fec82c7eea61','userid_4fec82c7eea61','2026-03-05 04:48:42'),(24,'product_trial','9','approve',NULL,NULL,'userid_4fec82c7eea61','userid_4fec82c7eea61','2026-03-05 05:54:06'),(25,'product_trial','8','approve',NULL,NULL,'userid_4fec82c7eea61','userid_4fec82c7eea61','2026-03-05 05:54:13'),(26,'bonus_survey','3','approve',NULL,NULL,'userid_4fec82c7eea61','userid_4fec82c7eea61','2026-03-05 05:54:22'),(27,'product_trial','21','approve',NULL,NULL,'userid_4fec82c7eea61','userid_4fec82c7eea61','2026-03-13 09:06:32'),(28,'product_trial','22','approve',NULL,NULL,'userid_d593d38eed2a1','userid_4fec82c7eea61','2026-03-15 08:57:10'),(29,'product_trial','23','approve',NULL,NULL,'userid_d593d38eed2a1','userid_4fec82c7eea61','2026-03-17 06:20:29'),(30,'product_trial','24','approve',NULL,NULL,'userid_4fec82c7eea61','userid_4fec82c7eea61','2026-03-17 07:48:12'),(31,'bonus_survey','5','approve',NULL,NULL,'userid_d593d38eed2a1','userid_4fec82c7eea61','2026-03-18 03:11:34'),(32,'bonus_survey','6','approve',NULL,NULL,'userid_d593d38eed2a1','userid_4fec82c7eea61','2026-03-24 06:17:21'),(33,'product_trial','25','approve',NULL,NULL,'userid_c60f522b273011f198b73a33889a1b82','userid_4fec82c7eea61','2026-03-24 06:20:52'),(34,'product_trial','26','approve',NULL,NULL,'userid_4fec82c7eea61','userid_4fec82c7eea61','2026-03-25 07:06:26'),(35,'product_trial','27','approve',NULL,NULL,'userid_8a6a4e1d29a711f198b73a33889a1b82','userid_4fec82c7eea61','2026-03-27 10:15:10'),(36,'product_trial','28','approve',NULL,NULL,'userid_8a6a4e1d29a711f198b73a33889a1b82','userid_4fec82c7eea61','2026-03-31 05:55:50'),(37,'bonus_survey','7','approve',NULL,NULL,'userid_8a6a4e1d29a711f198b73a33889a1b82','userid_4fec82c7eea61','2026-03-31 06:37:32');
/*!40000 ALTER TABLE `approval_actions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_login_attempts`
--

DROP TABLE IF EXISTS `auth_login_attempts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_login_attempts` (
  `AttemptID` bigint NOT NULL AUTO_INCREMENT,
  `Email` varchar(255) NOT NULL,
  `IP_Hash` char(64) NOT NULL,
  `AttemptedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `Successful` tinyint(1) NOT NULL DEFAULT '0',
  `UserAgent` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`AttemptID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_login_attempts`
--

LOCK TABLES `auth_login_attempts` WRITE;
/*!40000 ALTER TABLE `auth_login_attempts` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_login_attempts` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `bonus_survey_drafts`
--

DROP TABLE IF EXISTS `bonus_survey_drafts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `bonus_survey_drafts` (
  `bonus_survey_draft_id` int NOT NULL AUTO_INCREMENT,
  `created_by_user_id` varchar(32) NOT NULL,
  `status` varchar(16) NOT NULL DEFAULT 'draft',
  `title` varchar(255) NOT NULL,
  `description` text,
  `start_date` date DEFAULT NULL,
  `end_date` date DEFAULT NULL,
  `survey_link` text,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`bonus_survey_draft_id`),
  KEY `idx_creator` (`created_by_user_id`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `bonus_survey_drafts`
--

LOCK TABLES `bonus_survey_drafts` WRITE;
/*!40000 ALTER TABLE `bonus_survey_drafts` DISABLE KEYS */;
/*!40000 ALTER TABLE `bonus_survey_drafts` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `bonus_survey_participation`
--

DROP TABLE IF EXISTS `bonus_survey_participation`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `bonus_survey_participation` (
  `bonus_survey_participation_id` int NOT NULL AUTO_INCREMENT,
  `bonus_survey_id` int NOT NULL,
  `user_id` varchar(64) DEFAULT NULL,
  `completed_at` datetime DEFAULT NULL,
  `confirmation_source` varchar(64) NOT NULL COMMENT 'manual | import | webhook | audit',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `participation_token` varchar(64) DEFAULT NULL COMMENT 'UTS-generated token passed to external survey for correlation',
  `seen_at` datetime DEFAULT NULL,
  `started_at` datetime DEFAULT NULL,
  PRIMARY KEY (`bonus_survey_participation_id`),
  UNIQUE KEY `uq_bsp_user_survey` (`bonus_survey_id`,`user_id`),
  UNIQUE KEY `uniq_bonus_user` (`bonus_survey_id`,`user_id`),
  KEY `fk_bsp_user` (`user_id`),
  CONSTRAINT `fk_bsp_bonus_survey` FOREIGN KEY (`bonus_survey_id`) REFERENCES `bonus_surveys` (`bonus_survey_id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `bonus_survey_participation`
--

LOCK TABLES `bonus_survey_participation` WRITE;
/*!40000 ALTER TABLE `bonus_survey_participation` DISABLE KEYS */;
/*!40000 ALTER TABLE `bonus_survey_participation` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `bonus_survey_targeting_rules`
--

DROP TABLE IF EXISTS `bonus_survey_targeting_rules`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `bonus_survey_targeting_rules` (
  `RuleID` bigint NOT NULL AUTO_INCREMENT,
  `BonusSurveyID` bigint NOT NULL,
  `Criterion` varchar(64) NOT NULL,
  `Operator` varchar(16) NOT NULL DEFAULT '=',
  `Value` varchar(255) NOT NULL,
  `ValueType` varchar(32) NOT NULL,
  `Description` varchar(255) DEFAULT NULL,
  `CreatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `CreatedByUserID` varchar(64) NOT NULL,
  PRIMARY KEY (`RuleID`)
) ENGINE=InnoDB AUTO_INCREMENT=442 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `bonus_survey_targeting_rules`
--

LOCK TABLES `bonus_survey_targeting_rules` WRITE;
/*!40000 ALTER TABLE `bonus_survey_targeting_rules` DISABLE KEYS */;
INSERT INTO `bonus_survey_targeting_rules` VALUES (428,29,'job_function','IN','engineering','enum','Job function','2026-03-31 06:37:11','userid_4fec82c7eea61'),(429,29,'job_function','IN','design','enum','Job function','2026-03-31 06:37:11','userid_4fec82c7eea61'),(430,29,'job_function','IN','product','enum','Job function','2026-03-31 06:37:11','userid_4fec82c7eea61'),(431,29,'job_function','IN','marketing','enum','Job function','2026-03-31 06:37:11','userid_4fec82c7eea61'),(432,29,'job_function','IN','sales','enum','Job function','2026-03-31 06:37:11','userid_4fec82c7eea61'),(433,29,'job_function','IN','support','enum','Job function','2026-03-31 06:37:11','userid_4fec82c7eea61'),(434,29,'job_function','IN','operations','enum','Job function','2026-03-31 06:37:11','userid_4fec82c7eea61'),(435,29,'primary_os','IN','windows','enum','Primary operating system','2026-03-31 06:37:11','userid_4fec82c7eea61'),(436,29,'primary_os','IN','macos','enum','Primary operating system','2026-03-31 06:37:11','userid_4fec82c7eea61'),(437,29,'primary_os','IN','linux','enum','Primary operating system','2026-03-31 06:37:11','userid_4fec82c7eea61'),(438,29,'phone_os','IN','ios','enum','Primary phone OS','2026-03-31 06:37:11','userid_4fec82c7eea61'),(439,29,'gender','IN','female','enum','Self-reported gender','2026-03-31 06:37:11','userid_4fec82c7eea61'),(440,29,'gender','IN','male','enum','Self-reported gender','2026-03-31 06:37:11','userid_4fec82c7eea61'),(441,29,'gender','IN','nonbinary','enum','Self-reported gender','2026-03-31 06:37:11','userid_4fec82c7eea61');
/*!40000 ALTER TABLE `bonus_survey_targeting_rules` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `bonus_survey_tracker`
--

DROP TABLE IF EXISTS `bonus_survey_tracker`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `bonus_survey_tracker` (
  `tracker_id` bigint NOT NULL AUTO_INCREMENT,
  `survey_id` int NOT NULL,
  `current_state` enum('pending','changes_requested','active','rejected') NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `locked_at` datetime DEFAULT NULL,
  PRIMARY KEY (`tracker_id`),
  UNIQUE KEY `uq_bonus_survey_tracker_survey` (`survey_id`),
  CONSTRAINT `fk_bonus_survey_tracker_survey` FOREIGN KEY (`survey_id`) REFERENCES `bonus_surveys` (`bonus_survey_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `bonus_survey_tracker`
--

LOCK TABLES `bonus_survey_tracker` WRITE;
/*!40000 ALTER TABLE `bonus_survey_tracker` DISABLE KEYS */;
INSERT INTO `bonus_survey_tracker` VALUES (7,29,'pending','2026-03-31 06:37:11',NULL);
/*!40000 ALTER TABLE `bonus_survey_tracker` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `bonus_survey_tracker_entries`
--

DROP TABLE IF EXISTS `bonus_survey_tracker_entries`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `bonus_survey_tracker_entries` (
  `entry_id` bigint NOT NULL AUTO_INCREMENT,
  `tracker_id` bigint NOT NULL,
  `entry_type` enum('submitted','info_requested','info_response','changes_requested','resubmitted','approved','rejected') NOT NULL,
  `actor_user_id` varchar(64) NOT NULL,
  `reason_code` enum('more_information','request_change','unsuitable') DEFAULT NULL,
  `detail_text` text,
  `resolves_entry_id` bigint DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`entry_id`),
  KEY `fk_tracker_entries_tracker` (`tracker_id`),
  KEY `fk_tracker_entries_actor` (`actor_user_id`),
  KEY `fk_tracker_entries_resolves` (`resolves_entry_id`),
  CONSTRAINT `fk_tracker_entries_resolves` FOREIGN KEY (`resolves_entry_id`) REFERENCES `bonus_survey_tracker_entries` (`entry_id`),
  CONSTRAINT `fk_tracker_entries_tracker` FOREIGN KEY (`tracker_id`) REFERENCES `bonus_survey_tracker` (`tracker_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `bonus_survey_tracker_entries`
--

LOCK TABLES `bonus_survey_tracker_entries` WRITE;
/*!40000 ALTER TABLE `bonus_survey_tracker_entries` DISABLE KEYS */;
INSERT INTO `bonus_survey_tracker_entries` VALUES (9,7,'submitted','userid_4fec82c7eea61',NULL,NULL,NULL,'2026-03-31 06:37:11');
/*!40000 ALTER TABLE `bonus_survey_tracker_entries` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `bonus_surveys`
--

DROP TABLE IF EXISTS `bonus_surveys`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `bonus_surveys` (
  `bonus_survey_id` int NOT NULL AUTO_INCREMENT,
  `created_by_user_id` varchar(32) NOT NULL,
  `survey_title` varchar(255) NOT NULL,
  `survey_link` text NOT NULL,
  `response_destination` text NOT NULL,
  `open_at` datetime DEFAULT NULL,
  `close_at` datetime DEFAULT NULL,
  `status` varchar(32) DEFAULT NULL COMMENT 'pending_approval | approved | active | archived',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`bonus_survey_id`),
  KEY `fk_bonus_surveys_created_by_user` (`created_by_user_id`),
  CONSTRAINT `chk_bonus_surveys_status` CHECK ((`status` in (_utf8mb4'pending_approval',_utf8mb4'approved',_utf8mb4'active',_utf8mb4'archived')))
) ENGINE=InnoDB AUTO_INCREMENT=30 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `bonus_surveys`
--

LOCK TABLES `bonus_surveys` WRITE;
/*!40000 ALTER TABLE `bonus_surveys` DISABLE KEYS */;
INSERT INTO `bonus_surveys` VALUES (29,'userid_4fec82c7eea61','Autobots','https://docs.google.com/forms/d/e/1FAIpQLSdU-NcUwLggfxFFwWD9cP14__TcUX4q4q4tH24CX8pxvFcHWA/viewform?usp=pp_url&entry.1711341715=user_token_here','Energon Cubes','2026-03-25 00:00:00','2026-04-11 00:00:00','active','2026-03-31 06:37:11','2026-03-31 06:37:32');
/*!40000 ALTER TABLE `bonus_surveys` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `notification_delivery_log`
--

DROP TABLE IF EXISTS `notification_delivery_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `notification_delivery_log` (
  `delivery_id` bigint NOT NULL AUTO_INCREMENT,
  `notification_id` char(36) NOT NULL,
  `user_id` varchar(64) DEFAULT NULL,
  `channel` enum('in_app','email','sms') NOT NULL,
  `status` enum('sent','failed') NOT NULL,
  `error_message` text,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`delivery_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `notification_delivery_log`
--

LOCK TABLES `notification_delivery_log` WRITE;
/*!40000 ALTER TABLE `notification_delivery_log` DISABLE KEYS */;
/*!40000 ALTER TABLE `notification_delivery_log` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `notification_notifications`
--

DROP TABLE IF EXISTS `notification_notifications`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `notification_notifications` (
  `notification_id` char(36) NOT NULL,
  `notification_type_id` int NOT NULL,
  `payload` json DEFAULT NULL,
  `created_by` varchar(64) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`notification_id`),
  KEY `notification_type_id` (`notification_type_id`),
  CONSTRAINT `notification_notifications_ibfk_1` FOREIGN KEY (`notification_type_id`) REFERENCES `notification_types` (`notification_type_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `notification_notifications`
--

LOCK TABLES `notification_notifications` WRITE;
/*!40000 ALTER TABLE `notification_notifications` DISABLE KEYS */;
INSERT INTO `notification_notifications` VALUES ('07c2284f-f15e-4b1f-bd39-7bf12c9db27e',12,'{\"round_id\": 27}','userid_4fec82c7eea61','2026-03-27 10:15:11'),('67f623d8-fd7d-46da-b974-d34e1db37468',9,'{\"round_id\": 28, \"ut_lead_id\": \"userid_8a6a4e1d29a711f198b73a33889a1b82\"}','userid_4fec82c7eea61','2026-03-31 05:55:50'),('761549d0-d496-4a3b-b494-94491a5504bc',9,'{\"round_id\": 27, \"ut_lead_id\": \"userid_8a6a4e1d29a711f198b73a33889a1b82\"}','userid_4fec82c7eea61','2026-03-27 10:15:11'),('77dbc04a-6538-41b6-b231-d87a74d5f608',9,'{\"round_id\": 26, \"ut_lead_id\": \"userid_4fec82c7eea61\"}','userid_4fec82c7eea61','2026-03-25 07:06:26'),('81902520-4fba-4b24-9612-27efe0df5329',12,'{\"round_id\": 28}','userid_4fec82c7eea61','2026-03-31 05:55:50'),('8d480fe7-bb25-4af9-8c92-b846a8399bce',1,'{\"submitted_by\": \"userid_4fec82c7eea61\", \"survey_title\": \"Autobots\", \"bonus_survey_id\": 29}','userid_4fec82c7eea61','2026-03-31 06:37:11'),('a519808e-309c-4140-a680-63dfd64c89a0',2,'{\"project_id\": \"a5ccb898-1d40-4bed-a890-b2849dcd0e88\", \"trial_type\": \"ut_trial\", \"user_amount\": null, \"project_name\": \"Repeater 2\", \"requested_by\": \"userid_8a6a4e1d29a711f198b73a33889a1b82\", \"business_group\": \"Logi G\", \"product_category\": \"Gaming Mouse\", \"estimated_end_date\": null, \"estimated_start_date\": \"2026-04-13\"}','userid_8a6a4e1d29a711f198b73a33889a1b82','2026-03-27 07:04:42'),('af716d6b-bda6-4b6f-94c9-425990228768',2,'{\"project_id\": \"35d1bf56-79ef-45c5-be63-bc4303644bdb\", \"trial_type\": \"ut_trial\", \"user_amount\": null, \"project_name\": \"Yenn\", \"requested_by\": \"userid_4fec82c7eea61\", \"business_group\": \"Logi G\", \"product_category\": \"Headset\", \"estimated_end_date\": null, \"estimated_start_date\": \"2026-07-01\"}','userid_4fec82c7eea61','2026-03-31 05:52:41'),('bee6ac9f-1b2c-4ae4-b3cd-e766177bef17',10,'{\"survey_title\": \"Autobots\", \"bonus_survey_id\": 29}','userid_4fec82c7eea61','2026-03-31 06:37:32'),('c5e3ea41-89b2-49a4-b638-11dbb40ef1f2',12,'{\"round_id\": 26}','userid_4fec82c7eea61','2026-03-25 07:06:26'),('e17eef0c-81c7-45d1-a048-b11f12d4eeae',2,'{\"project_id\": \"3f2e7eb8-bd11-4d03-9919-af882becb0a8\", \"trial_type\": \"ut_trial\", \"user_amount\": null, \"project_name\": \"Remo\", \"requested_by\": \"userid_4fec82c7eea61\", \"business_group\": \"Logi G & C\", \"product_category\": \"Blue Microphone\", \"estimated_end_date\": null, \"estimated_start_date\": \"2026-04-25\"}','userid_4fec82c7eea61','2026-03-25 06:28:10');
/*!40000 ALTER TABLE `notification_notifications` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `notification_recipients`
--

DROP TABLE IF EXISTS `notification_recipients`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `notification_recipients` (
  `notification_recipient_id` bigint NOT NULL AUTO_INCREMENT,
  `notification_id` char(36) NOT NULL,
  `user_id` varchar(64) DEFAULT NULL,
  `is_read` tinyint(1) NOT NULL DEFAULT '0',
  `read_at` datetime DEFAULT NULL,
  `is_dismissed` tinyint(1) NOT NULL DEFAULT '0',
  `dismissed_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`notification_recipient_id`),
  UNIQUE KEY `uniq_notification_user` (`notification_id`,`user_id`),
  CONSTRAINT `notification_recipients_ibfk_1` FOREIGN KEY (`notification_id`) REFERENCES `notification_notifications` (`notification_id`)
) ENGINE=InnoDB AUTO_INCREMENT=71 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `notification_recipients`
--

LOCK TABLES `notification_recipients` WRITE;
/*!40000 ALTER TABLE `notification_recipients` DISABLE KEYS */;
INSERT INTO `notification_recipients` VALUES (60,'e17eef0c-81c7-45d1-a048-b11f12d4eeae','userid_4fec82c7eea61',1,'2026-03-25 06:29:18',0,NULL,'2026-03-25 06:28:10'),(61,'77dbc04a-6538-41b6-b231-d87a74d5f608','userid_4fec82c7eea61',1,'2026-03-25 07:06:32',0,NULL,'2026-03-25 07:06:26'),(62,'c5e3ea41-89b2-49a4-b638-11dbb40ef1f2','userid_4fec82c7eea61',1,'2026-03-25 07:06:32',0,NULL,'2026-03-25 07:06:26'),(63,'a519808e-309c-4140-a680-63dfd64c89a0','userid_4fec82c7eea61',1,'2026-03-27 10:14:47',0,NULL,'2026-03-27 07:04:42'),(64,'761549d0-d496-4a3b-b494-94491a5504bc','userid_8a6a4e1d29a711f198b73a33889a1b82',0,NULL,0,NULL,'2026-03-27 10:15:11'),(65,'07c2284f-f15e-4b1f-bd39-7bf12c9db27e','userid_8a6a4e1d29a711f198b73a33889a1b82',0,NULL,0,NULL,'2026-03-27 10:15:11'),(66,'af716d6b-bda6-4b6f-94c9-425990228768','userid_4fec82c7eea61',1,'2026-03-31 05:52:51',0,NULL,'2026-03-31 05:52:41'),(67,'67f623d8-fd7d-46da-b974-d34e1db37468','userid_4fec82c7eea61',1,'2026-03-31 05:57:23',0,NULL,'2026-03-31 05:55:50'),(68,'81902520-4fba-4b24-9612-27efe0df5329','userid_8a6a4e1d29a711f198b73a33889a1b82',0,NULL,0,NULL,'2026-03-31 05:55:50'),(69,'8d480fe7-bb25-4af9-8c92-b846a8399bce','userid_4fec82c7eea61',1,'2026-03-31 06:37:53',0,NULL,'2026-03-31 06:37:11'),(70,'bee6ac9f-1b2c-4ae4-b3cd-e766177bef17','userid_4fec82c7eea61',1,'2026-03-31 06:37:53',0,NULL,'2026-03-31 06:37:32');
/*!40000 ALTER TABLE `notification_recipients` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `notification_types`
--

DROP TABLE IF EXISTS `notification_types`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `notification_types` (
  `notification_type_id` int NOT NULL AUTO_INCREMENT,
  `type_key` varchar(64) NOT NULL,
  `title` varchar(128) NOT NULL,
  `description` text,
  `severity` enum('info','warning','action','critical') DEFAULT 'info',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `approval_intent` varchar(64) DEFAULT NULL,
  PRIMARY KEY (`notification_type_id`),
  UNIQUE KEY `type_key` (`type_key`)
) ENGINE=InnoDB AUTO_INCREMENT=19 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `notification_types`
--

LOCK TABLES `notification_types` WRITE;
/*!40000 ALTER TABLE `notification_types` DISABLE KEYS */;
INSERT INTO `notification_types` VALUES (1,'bonus_survey_pending_approval','Bonus Survey Pending Approval','A bonus survey has been submitted and is awaiting review.','info','2026-01-25 06:56:33',NULL),(2,'product_trial_pending_approval','Product Trial Pending Approval','A product team user trial request has been submitted and is awaiting UT review.','info','2026-02-05 05:44:57','ut_review'),(3,'product_trial_declined','Product Trial Declined','Your product trial request has been declined. Please review the provided reason.','warning','2026-02-06 07:10:59','decline'),(4,'bonus_survey_declined','Bonus Survey Declined','Your bonus survey request has been declined. Please review the provided reason.','warning','2026-02-06 07:10:59','decline'),(5,'product_trial_info_requested','More Information Requested for Product Trial','The UT Lead has requested additional information for your product trial request.','info','2026-02-06 07:11:05','request_info'),(6,'bonus_survey_info_requested','More Information Requested for Bonus Survey','The UT Lead has requested additional information for your bonus survey request.','info','2026-02-06 07:11:05','request_info'),(7,'product_trial_changes_requested','Changes Requested for Product Trial','Changes are required before your product trial can be approved.','info','2026-02-06 07:11:15','request_changes'),(8,'bonus_survey_changes_requested','Changes Requested for Bonus Survey','Changes are required before your bonus survey can be approved.','info','2026-02-06 07:11:15','request_changes'),(9,'product_trial_approved','Product Trial Approved','Your product trial request has been approved and will proceed.','info','2026-02-06 07:14:01','approve'),(10,'bonus_survey_approved','Bonus Survey Approved','Your bonus survey request has been approved and is now active.','info','2026-02-06 07:14:01','approve'),(11,'product_trial_change_requested','Changes requested for product trial','UT has reviewed your request and requires changes before approval.','warning','2026-02-06 12:06:31',NULL),(12,'product_trial_assigned','Product Trial Assigned','You have been assigned as the UT Lead for a product trial.','action','2026-02-09 07:14:21','approve'),(13,'product_trial_change_accepted','Changes Accepted','The product team has accepted the requested changes.','info','2026-02-09 07:14:21',NULL),(14,'product_trial_change_countered','Changes Countered','The product team has proposed an alternative to the requested changes.','info','2026-02-09 07:14:21',NULL),(15,'product_trial_withdrawn_by_requestor','Product Trial Withdrawn','The product team has withdrawn their trial request.','warning','2026-02-09 07:14:21','decline'),(16,'trial_watch_registered','Trial Watch Registered','User requested notification when a trial begins recruiting','info','2026-03-05 05:00:53',NULL),(17,'trial_recruiting_started','Trial Recruiting Started','A trial you are watching has begun recruiting','info','2026-03-05 05:36:15',NULL),(18,'trial_recruiting_open','Recruiting is Open','A trial you are watching has started recruiting','info','2026-03-05 08:00:44',NULL);
/*!40000 ALTER TABLE `notification_types` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `project_applicants`
--

DROP TABLE IF EXISTS `project_applicants`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `project_applicants` (
  `ApplicantID` int NOT NULL AUTO_INCREMENT,
  `RoundID` int NOT NULL,
  `user_id` varchar(64) DEFAULT NULL,
  `AppliedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `MotivationText` text,
  `MotivationScore` decimal(5,2) DEFAULT NULL,
  `MatchScore` decimal(5,2) DEFAULT NULL,
  `ReliabilityScoreSnapshot` decimal(5,2) DEFAULT NULL,
  `ScreeningStatus` enum('Applied','Screening','Eligible','Ineligible','Invited','Selected','Rejected','Withdrawn','Declined') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'Applied',
  `EligibilityResult` enum('Eligible','Ineligible') DEFAULT NULL,
  `FinalDecision` enum('Selected','Rejected','Waitlisted','Withdrawn') DEFAULT NULL,
  `DecisionReason` text,
  `CreatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `UpdatedAt` datetime DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  `ApplicationSource` enum('Internal','External') NOT NULL DEFAULT 'Internal',
  `ApplicationStatus` enum('PendingExternal','Confirmed') NOT NULL DEFAULT 'Confirmed',
  `ExternalSurveyCompletedAt` datetime DEFAULT NULL,
  PRIMARY KEY (`ApplicantID`),
  UNIQUE KEY `uniq_round_user` (`RoundID`,`user_id`),
  KEY `RoundID` (`RoundID`),
  KEY `UserID` (`user_id`),
  CONSTRAINT `project_applicants_ibfk_1` FOREIGN KEY (`RoundID`) REFERENCES `project_rounds` (`RoundID`),
  CONSTRAINT `project_applicants_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `user_pool` (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=15 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `project_applicants`
--

LOCK TABLES `project_applicants` WRITE;
/*!40000 ALTER TABLE `project_applicants` DISABLE KEYS */;
INSERT INTO `project_applicants` VALUES (14,26,'userid_4fec82c7eea61','2026-03-30 08:33:11',NULL,NULL,NULL,NULL,'Applied',NULL,NULL,NULL,'2026-03-30 08:33:11',NULL,'Internal','Confirmed',NULL);
/*!40000 ALTER TABLE `project_applicants` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `project_ndas`
--

DROP TABLE IF EXISTS `project_ndas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `project_ndas` (
  `NDAID` int NOT NULL AUTO_INCREMENT,
  `user_id` varchar(64) DEFAULT NULL,
  `ProjectID` varchar(48) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `RoundID` int NOT NULL,
  `ParticipantID` int DEFAULT NULL,
  `NDAStatus` enum('Pending','Unconfirmed','Signed','Expired','Superseded') NOT NULL DEFAULT 'Pending',
  `DocumentHash` char(64) NOT NULL,
  `HashAlgorithm` varchar(20) NOT NULL DEFAULT 'SHA-256',
  `FilePath` varchar(512) NOT NULL,
  `DateSent` datetime NOT NULL,
  `DateSigned` datetime DEFAULT NULL,
  `DateReceived` datetime DEFAULT NULL,
  `UpdatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`NDAID`),
  KEY `idx_ndas_user` (`user_id`),
  KEY `idx_ndas_project_round` (`ProjectID`,`RoundID`),
  KEY `idx_ndas_participant` (`ParticipantID`),
  KEY `fk_ndas_round` (`RoundID`),
  CONSTRAINT `fk_ndas_participant` FOREIGN KEY (`ParticipantID`) REFERENCES `project_participants` (`ParticipantID`),
  CONSTRAINT `fk_ndas_project` FOREIGN KEY (`ProjectID`) REFERENCES `project_projects` (`ProjectID`),
  CONSTRAINT `fk_ndas_round` FOREIGN KEY (`RoundID`) REFERENCES `project_rounds` (`RoundID`),
  CONSTRAINT `fk_ndas_user` FOREIGN KEY (`user_id`) REFERENCES `user_pool` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `project_ndas`
--

LOCK TABLES `project_ndas` WRITE;
/*!40000 ALTER TABLE `project_ndas` DISABLE KEYS */;
/*!40000 ALTER TABLE `project_ndas` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `project_participants`
--

DROP TABLE IF EXISTS `project_participants`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `project_participants` (
  `ParticipantID` int NOT NULL AUTO_INCREMENT,
  `RoundID` int NOT NULL,
  `user_id` varchar(64) DEFAULT NULL,
  `DeliveryType` enum('Home','Office') NOT NULL,
  `DeliveryAddressID` int DEFAULT NULL,
  `OfficeID` varchar(20) DEFAULT NULL,
  `Courier` varchar(100) DEFAULT NULL,
  `TrackingNumber` varchar(100) DEFAULT NULL,
  `ShippedAt` datetime DEFAULT NULL,
  `DeliveredAt` datetime DEFAULT NULL,
  `SelectedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `RoundNDA_SignedAt` datetime DEFAULT NULL,
  `ParticipantStatus` enum('Selected','Active','Completed','Dropped','Disqualified') NOT NULL DEFAULT 'Selected',
  `CompletedAt` datetime DEFAULT NULL,
  `DroppedReason` text,
  `Notes` text,
  `CreatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `UpdatedAt` datetime DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  `SourceApplicantID` int DEFAULT NULL,
  `TrialNickname` varchar(50) NOT NULL,
  `NicknameSource` enum('SystemSuggested','UserSelected') NOT NULL DEFAULT 'SystemSuggested',
  `ProfileSnapshotCode` varchar(500) NOT NULL,
  PRIMARY KEY (`ParticipantID`),
  UNIQUE KEY `uniq_trial_nickname` (`RoundID`,`TrialNickname`),
  KEY `UserID` (`user_id`),
  KEY `fk_participant_source_applicant` (`SourceApplicantID`),
  KEY `idx_delivery_home` (`DeliveryAddressID`),
  KEY `idx_delivery_office` (`OfficeID`),
  CONSTRAINT `fk_participant_home_address` FOREIGN KEY (`DeliveryAddressID`) REFERENCES `user_home_address` (`HomeAddressID`),
  CONSTRAINT `fk_participant_office` FOREIGN KEY (`OfficeID`) REFERENCES `system_office_locations` (`OfficeID`),
  CONSTRAINT `fk_participant_source_applicant` FOREIGN KEY (`SourceApplicantID`) REFERENCES `project_applicants` (`ApplicantID`),
  CONSTRAINT `project_participants_ibfk_1` FOREIGN KEY (`RoundID`) REFERENCES `project_rounds` (`RoundID`),
  CONSTRAINT `project_participants_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `user_pool` (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=45 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `project_participants`
--

LOCK TABLES `project_participants` WRITE;
/*!40000 ALTER TABLE `project_participants` DISABLE KEYS */;
/*!40000 ALTER TABLE `project_participants` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `project_projects`
--

DROP TABLE IF EXISTS `project_projects`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `project_projects` (
  `ProjectID` varchar(48) NOT NULL,
  `ProjectName` varchar(255) NOT NULL,
  `MarketName` varchar(100) NOT NULL,
  `GateX_Date` date DEFAULT NULL,
  `BusinessGroup` varchar(100) NOT NULL,
  `BusinessSubGroup` varchar(255) DEFAULT NULL,
  `ProductType` varchar(150) DEFAULT NULL,
  `Description` text,
  `MinAge` int DEFAULT NULL,
  `MaxAge` int DEFAULT NULL,
  `GuardianRequired` tinyint(1) DEFAULT NULL,
  `PRD_Document` varchar(255) DEFAULT NULL,
  `G1_Document` varchar(255) DEFAULT NULL,
  `G0_Document` varchar(255) DEFAULT NULL,
  `AdditionalDocs` text,
  `CreatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `UpdatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `CreatedBy` varchar(48) NOT NULL,
  `ProjectStatus` varchar(50) NOT NULL DEFAULT 'draft',
  PRIMARY KEY (`ProjectID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `project_projects`
--

LOCK TABLES `project_projects` WRITE;
/*!40000 ALTER TABLE `project_projects` DISABLE KEYS */;
INSERT INTO `project_projects` VALUES ('35d1bf56-79ef-45c5-be63-bc4303644bdb','Yenn','G999',NULL,'Logi G','unspecified','Headset','Newest and Greatest Headset with Stand',18,99,0,NULL,NULL,NULL,NULL,'2026-03-31 05:52:41','2026-03-31 05:52:41','userid_4fec82c7eea61','draft'),('3f2e7eb8-bd11-4d03-9919-af882becb0a8','Remo','Logi Blue Yeti 2',NULL,'Logi G & C','unspecified','Blue Microphone','Refresh of the classic Yeti.',18,99,0,NULL,NULL,NULL,NULL,'2026-03-25 06:28:10','2026-03-25 06:28:10','userid_4fec82c7eea61','draft'),('a5ccb898-1d40-4bed-a890-b2849dcd0e88','Repeater 2','Pro X3 Superstrike',NULL,'Logi G','unspecified','Gaming Mouse','Check new pcb and USB receiver',18,99,0,NULL,NULL,NULL,NULL,'2026-03-27 07:04:42','2026-03-27 07:04:42','userid_8a6a4e1d29a711f198b73a33889a1b82','draft');
/*!40000 ALTER TABLE `project_projects` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `project_round_interest`
--

DROP TABLE IF EXISTS `project_round_interest`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `project_round_interest` (
  `InterestID` bigint unsigned NOT NULL AUTO_INCREMENT,
  `RoundID` int NOT NULL,
  `user_id` varchar(64) DEFAULT NULL,
  `CreatedAt` datetime DEFAULT CURRENT_TIMESTAMP,
  `NotifiedAt` datetime DEFAULT NULL,
  PRIMARY KEY (`InterestID`),
  UNIQUE KEY `uniq_round_user` (`RoundID`,`user_id`),
  UNIQUE KEY `RoundID` (`RoundID`,`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `project_round_interest`
--

LOCK TABLES `project_round_interest` WRITE;
/*!40000 ALTER TABLE `project_round_interest` DISABLE KEYS */;
INSERT INTO `project_round_interest` VALUES (5,27,'userid_4fec82c7eea61','2026-03-31 04:49:59',NULL),(6,28,'userid_4fec82c7eea61','2026-03-31 06:09:04',NULL);
/*!40000 ALTER TABLE `project_round_interest` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `project_round_surveys`
--

DROP TABLE IF EXISTS `project_round_surveys`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `project_round_surveys` (
  `RoundSurveyID` bigint unsigned NOT NULL AUTO_INCREMENT,
  `RoundID` int NOT NULL,
  `SurveyTypeID` varchar(20) NOT NULL,
  `SurveyLink` text NOT NULL,
  `SurveyDistributionLink` text,
  `IsActive` tinyint(1) NOT NULL DEFAULT '1',
  `CreatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `CreatedByUserID` varchar(20) NOT NULL,
  `SupersedesID` bigint unsigned DEFAULT NULL,
  PRIMARY KEY (`RoundSurveyID`),
  KEY `idx_round` (`RoundID`),
  KEY `idx_type` (`SurveyTypeID`),
  KEY `idx_active` (`IsActive`),
  KEY `fk_round_surveys_user` (`CreatedByUserID`),
  KEY `fk_round_surveys_supersedes` (`SupersedesID`),
  CONSTRAINT `fk_round_surveys_round` FOREIGN KEY (`RoundID`) REFERENCES `project_rounds` (`RoundID`) ON DELETE CASCADE,
  CONSTRAINT `fk_round_surveys_supersedes` FOREIGN KEY (`SupersedesID`) REFERENCES `project_round_surveys` (`RoundSurveyID`) ON DELETE SET NULL,
  CONSTRAINT `fk_round_surveys_type` FOREIGN KEY (`SurveyTypeID`) REFERENCES `survey_types` (`SurveyTypeID`) ON DELETE RESTRICT
) ENGINE=InnoDB AUTO_INCREMENT=23 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `project_round_surveys`
--

LOCK TABLES `project_round_surveys` WRITE;
/*!40000 ALTER TABLE `project_round_surveys` DISABLE KEYS */;
INSERT INTO `project_round_surveys` VALUES (16,26,'UTSurveyType0001','https://docs.google.com/forms/d/1giwKCIKvG8TsZl8Ur4wLPn4L-mvp0BmzoQnZVeu-k0A/edit','https://docs.google.com/forms/d/e/1FAIpQLSfs2e_FWkcYXCfXcq1hpCfg6MmV5qRnJ7COlQIhDPK1fHVRdQ/viewform?usp=pp_url&entry.648734718=user_token_here',0,'2026-03-25 08:47:44','userid_4fec82c7eea61',NULL),(17,26,'UTSurveyType0027','https://docs.google.com/forms/d/1bAvOKKR0pQDEug6Pb5KJUDhup-CSZygZJz-i8gjTffg/edit','',1,'2026-03-25 08:54:39','userid_4fec82c7eea61',NULL),(18,26,'UTSurveyType1001','','https://docs.google.com/forms/d/e/1FAIpQLSe95KHUhSD7_UFVrIOiyfbsIxCU9IhkWPLbcUp_7Ii71qmypQ/viewform?usp=pp_url&entry.1286199023=user_token_here',1,'2026-03-25 10:04:00','userid_4fec82c7eea61',NULL),(19,26,'UTSurveyType0001','https://docs.google.com/forms/d/1giwKCIKvG8TsZl8Ur4wLPn4L-mvp0BmzoQnZVeu-k0A/edit','https://docs.google.com/forms/d/e/1FAIpQLSfs2e_FWkcYXCfXcq1hpCfg6MmV5qRnJ7COlQIhDPK1fHVRdQ/viewform?usp=pp_url&entry.648734718=user_token_here',0,'2026-03-26 10:21:26','userid_4fec82c7eea61',NULL),(20,26,'UTSurveyType0001','','https://docs.google.com/forms/d/e/1FAIpQLSe95KHUhSD7_UFVrIOiyfbsIxCU9IhkWPLbcUp_7Ii71qmypQ/viewform?usp=pp_url&entry.1286199023=user_token_here',0,'2026-03-27 10:20:49','userid_4fec82c7eea61',NULL),(21,26,'UTSurveyType0001','','https://docs.google.com/forms/d/e/1FAIpQLSfs2e_FWkcYXCfXcq1hpCfg6MmV5qRnJ7COlQIhDPK1fHVRdQ/viewform?usp=pp_url&entry.648734718=user_token_here',0,'2026-03-30 08:11:53','userid_4fec82c7eea61',NULL),(22,26,'UTSurveyType0001','','https://docs.google.com/forms/d/e/1FAIpQLSfs2e_FWkcYXCfXcq1hpCfg6MmV5qRnJ7COlQIhDPK1fHVRdQ/viewform?usp=pp_url&entry.648734718=user_token_here',1,'2026-03-30 08:17:51','userid_4fec82c7eea61',NULL);
/*!40000 ALTER TABLE `project_round_surveys` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `project_rounds`
--

DROP TABLE IF EXISTS `project_rounds`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `project_rounds` (
  `RoundID` int NOT NULL AUTO_INCREMENT,
  `ProjectID` varchar(48) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `RoundNumber` int NOT NULL,
  `RoundName` varchar(255) DEFAULT NULL,
  `Description` text,
  `StartDate` date DEFAULT NULL,
  `EndDate` date DEFAULT NULL,
  `Region` varchar(100) NOT NULL,
  `UserScope` enum('Internal','External','Hybrid') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT 'Hybrid',
  `TargetUsers` int DEFAULT NULL,
  `ShipDate` date DEFAULT NULL,
  `GateX_Date` date DEFAULT NULL,
  `MinAge` int DEFAULT NULL,
  `MaxAge` int DEFAULT NULL,
  `PrototypeVersion` varchar(100) DEFAULT NULL,
  `ProductSKU` varchar(50) DEFAULT NULL,
  `UTLead_UserID` varchar(48) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `Status` varchar(32) NOT NULL DEFAULT 'pending_ut_review',
  `RecruitingStartDate` date DEFAULT NULL,
  `CreatedAt` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `UpdatedAt` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `OverviewLocked` tinyint(1) NOT NULL DEFAULT '0',
  `OverviewLockedAt` datetime DEFAULT NULL,
  `OverviewLockedBy` varchar(64) DEFAULT NULL,
  `ParticipantsLocked` tinyint(1) NOT NULL DEFAULT '0',
  `ParticipantsLockedAt` datetime DEFAULT NULL,
  `ParticipantsLockedBy` varchar(64) DEFAULT NULL,
  `SurveyResultsLocked` tinyint(1) NOT NULL DEFAULT '0',
  `SurveyResultsLockedAt` datetime DEFAULT NULL,
  `SurveyResultsLockedBy` varchar(64) DEFAULT NULL,
  `CompletedAt` datetime DEFAULT NULL,
  `PlanningLocked` tinyint(1) NOT NULL DEFAULT '0',
  `PlanningLockedAt` datetime DEFAULT NULL,
  `PlanningLockedBy` varchar(64) DEFAULT NULL,
  `ProfileLocked` tinyint(1) DEFAULT '0',
  `ProfileLockedAt` datetime DEFAULT NULL,
  `ProfileLockedBy` varchar(64) DEFAULT NULL,
  `RecruitingEndDate` date DEFAULT NULL,
  `UseExternalRecruitingSurvey` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`RoundID`),
  KEY `ProjectID` (`ProjectID`),
  KEY `UTLead_UserID` (`UTLead_UserID`),
  CONSTRAINT `project_rounds_ibfk_1` FOREIGN KEY (`ProjectID`) REFERENCES `project_projects` (`ProjectID`)
) ENGINE=InnoDB AUTO_INCREMENT=29 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `project_rounds`
--

LOCK TABLES `project_rounds` WRITE;
/*!40000 ALTER TABLE `project_rounds` DISABLE KEYS */;
INSERT INTO `project_rounds` VALUES (26,'3f2e7eb8-bd11-4d03-9919-af882becb0a8',1,'Remo – Round 1','Refresh of the classic Yeti.','2026-03-09','2026-04-08','US,TW,CN,IN,IE,CH','Internal',45,'2026-03-02',NULL,19,61,'pb1','','userid_4fec82c7eea61','closed','2026-03-30','2026-03-25 06:28:10','2026-03-30 11:47:09',1,'2026-03-25 08:46:11','userid_4fec82c7eea61',0,NULL,NULL,0,NULL,NULL,NULL,1,'2026-03-30 11:47:09','userid_4fec82c7eea61',1,'2026-03-25 08:46:52','userid_4fec82c7eea61','2026-03-30',1),(27,'a5ccb898-1d40-4bed-a890-b2849dcd0e88',1,'Repeater 2 – Round 1','','2026-04-22','2026-05-22','TW,CN,CH,KP,GB,DE,NL','Hybrid',30,'2026-03-31',NULL,NULL,NULL,'pb1.5','','userid_8a6a4e1d29a711f198b73a33889a1b82','approved',NULL,'2026-03-27 07:04:42','2026-03-31 05:12:02',0,NULL,NULL,0,NULL,NULL,0,NULL,NULL,NULL,0,NULL,NULL,1,'2026-03-31 05:11:20','userid_8a6a4e1d29a711f198b73a33889a1b82',NULL,1),(28,'35d1bf56-79ef-45c5-be63-bc4303644bdb',1,'Yenn – Round 1',NULL,NULL,NULL,'TW,US,NL','Hybrid',0,NULL,NULL,18,99,NULL,NULL,'userid_8a6a4e1d29a711f198b73a33889a1b82','approved',NULL,'2026-03-31 05:52:41','2026-03-31 05:55:50',0,NULL,NULL,0,NULL,NULL,0,NULL,NULL,NULL,0,NULL,NULL,0,NULL,NULL,NULL,0);
/*!40000 ALTER TABLE `project_rounds` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `project_stakeholders`
--

DROP TABLE IF EXISTS `project_stakeholders`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `project_stakeholders` (
  `StakeholderID` int NOT NULL AUTO_INCREMENT,
  `ProjectID` varchar(48) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `Email` varchar(255) DEFAULT NULL,
  `DisplayName` varchar(255) NOT NULL,
  `user_id` varchar(64) DEFAULT NULL,
  `StakeholderRole` enum('GPM','PM','PQA') NOT NULL,
  `IsPrimary` tinyint(1) NOT NULL DEFAULT '0',
  `Active` tinyint(1) NOT NULL DEFAULT '1',
  `AssignedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `Notes` text,
  `RoundID` int NOT NULL,
  PRIMARY KEY (`StakeholderID`),
  KEY `ProjectID` (`ProjectID`),
  KEY `UserID` (`user_id`),
  KEY `idx_project_stakeholders_email` (`Email`),
  CONSTRAINT `project_stakeholders_ibfk_1` FOREIGN KEY (`ProjectID`) REFERENCES `project_projects` (`ProjectID`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `project_stakeholders_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `user_pool` (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=43 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `project_stakeholders`
--

LOCK TABLES `project_stakeholders` WRITE;
/*!40000 ALTER TABLE `project_stakeholders` DISABLE KEYS */;
INSERT INTO `project_stakeholders` VALUES (35,'3f2e7eb8-bd11-4d03-9919-af882becb0a8',NULL,'Soren Pederson',NULL,'GPM',0,1,'2026-03-25 06:28:10',NULL,26),(36,'3f2e7eb8-bd11-4d03-9919-af882becb0a8',NULL,'Tiffany Chen',NULL,'PM',0,1,'2026-03-25 06:28:10',NULL,26),(37,'3f2e7eb8-bd11-4d03-9919-af882becb0a8',NULL,'Waylon Hsu',NULL,'PQA',0,1,'2026-03-25 06:28:10',NULL,26),(38,'a5ccb898-1d40-4bed-a890-b2849dcd0e88',NULL,'Arpit Chaudhary',NULL,'GPM',0,1,'2026-03-27 07:04:42',NULL,27),(39,'a5ccb898-1d40-4bed-a890-b2849dcd0e88',NULL,'chris Pike',NULL,'PM',0,1,'2026-03-27 07:04:42',NULL,27),(40,'35d1bf56-79ef-45c5-be63-bc4303644bdb',NULL,'Greg Gervin',NULL,'GPM',0,1,'2026-03-31 05:52:41',NULL,28),(41,'35d1bf56-79ef-45c5-be63-bc4303644bdb',NULL,'Louis Lee',NULL,'PM',0,1,'2026-03-31 05:52:41',NULL,28),(42,'35d1bf56-79ef-45c5-be63-bc4303644bdb',NULL,'Kenny Teng',NULL,'PQA',0,1,'2026-03-31 05:52:41',NULL,28);
/*!40000 ALTER TABLE `project_stakeholders` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `round_profile_criteria`
--

DROP TABLE IF EXISTS `round_profile_criteria`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `round_profile_criteria` (
  `RoundCriteriaID` int NOT NULL AUTO_INCREMENT,
  `RoundID` int NOT NULL,
  `ProfileUID` varchar(20) NOT NULL,
  `Operator` enum('INCLUDE','EXCLUDE') NOT NULL DEFAULT 'INCLUDE',
  `CreatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`RoundCriteriaID`),
  KEY `idx_round_id` (`RoundID`),
  KEY `idx_profile_uid` (`ProfileUID`),
  CONSTRAINT `fk_rpc_round` FOREIGN KEY (`RoundID`) REFERENCES `project_rounds` (`RoundID`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=27 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `round_profile_criteria`
--

LOCK TABLES `round_profile_criteria` WRITE;
/*!40000 ALTER TABLE `round_profile_criteria` DISABLE KEYS */;
INSERT INTO `round_profile_criteria` VALUES (20,26,'ProfileUID_00048','INCLUDE','2026-03-25 08:46:42'),(21,27,'ProfileUID_00001','INCLUDE','2026-03-31 05:07:44'),(22,27,'ProfileUID_00002','INCLUDE','2026-03-31 05:08:04'),(23,27,'ProfileUID_00003','INCLUDE','2026-03-31 05:08:21'),(24,27,'ProfileUID_00054','INCLUDE','2026-03-31 05:10:33'),(25,27,'ProfileUID_00054','INCLUDE','2026-03-31 05:10:35'),(26,27,'ProfileUID_00057','INCLUDE','2026-03-31 05:10:57');
/*!40000 ALTER TABLE `round_profile_criteria` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `round_stakeholders`
--

DROP TABLE IF EXISTS `round_stakeholders`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `round_stakeholders` (
  `RoundStakeholderID` int NOT NULL AUTO_INCREMENT,
  `RoundID` int NOT NULL,
  `Email` varchar(255) DEFAULT NULL,
  `DisplayName` varchar(255) DEFAULT NULL,
  `user_id` varchar(64) DEFAULT NULL,
  `StakeholderRole` varchar(64) DEFAULT NULL,
  `IsPrimary` tinyint(1) NOT NULL DEFAULT '0',
  `Active` tinyint(1) NOT NULL DEFAULT '1',
  `AssignedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `Notes` text,
  `CreatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `UpdatedAt` datetime DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`RoundStakeholderID`),
  KEY `idx_round_stakeholders_roundid` (`RoundID`),
  CONSTRAINT `fk_round_stakeholders_round` FOREIGN KEY (`RoundID`) REFERENCES `project_rounds` (`RoundID`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=32 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `round_stakeholders`
--

LOCK TABLES `round_stakeholders` WRITE;
/*!40000 ALTER TABLE `round_stakeholders` DISABLE KEYS */;
/*!40000 ALTER TABLE `round_stakeholders` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `scoring_model`
--

DROP TABLE IF EXISTS `scoring_model`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `scoring_model` (
  `ModelID` int NOT NULL AUTO_INCREMENT,
  `ModelName` varchar(100) NOT NULL,
  `Weight_Completion` decimal(5,2) NOT NULL,
  `Weight_Quality` decimal(5,2) NOT NULL,
  `Weight_Thought` decimal(5,2) NOT NULL,
  `Weight_Penalty` decimal(5,2) NOT NULL,
  `DecayFactor` decimal(5,2) DEFAULT NULL,
  `MinTrialsRequired` int DEFAULT '1',
  `Active` tinyint(1) NOT NULL DEFAULT '1',
  `CreatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `UpdatedAt` datetime DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`ModelID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `scoring_model`
--

LOCK TABLES `scoring_model` WRITE;
/*!40000 ALTER TABLE `scoring_model` DISABLE KEYS */;
/*!40000 ALTER TABLE `scoring_model` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `settings_definition`
--

DROP TABLE IF EXISTS `settings_definition`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `settings_definition` (
  `SettingKey` varchar(100) NOT NULL,
  `SettingName` varchar(150) NOT NULL,
  `SettingDescription` text,
  `DefaultValue` varchar(255) DEFAULT NULL,
  `AllowedValues` varchar(500) DEFAULT NULL,
  `DataType` enum('string','int','float','boolean','json') NOT NULL DEFAULT 'string',
  `Scope` enum('System','User','Hybrid') NOT NULL,
  PRIMARY KEY (`SettingKey`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `settings_definition`
--

LOCK TABLES `settings_definition` WRITE;
/*!40000 ALTER TABLE `settings_definition` DISABLE KEYS */;
INSERT INTO `settings_definition` VALUES ('auto_blacklist_threshold','Auto Blacklist Threshold','Number of missed deadlines before participant is blacklisted.','3',NULL,'int','System'),('compact_mode','Compact Mode','Reduces whitespace for dense UI layouts.','Off','On,Off','boolean','User'),('default_nda_reminder_limit','Default NDA Reminder Limit','System-wide maximum number of NDA reminders.','3',NULL,'int','System'),('default_survey_reminder_limit','Default Survey Reminder Limit','Maximum automated survey reminders per project.','3',NULL,'int','System'),('device_verification_required','Device Verification Required','Requires trusted device validation for login.','Off','On,Off','boolean','System'),('font_size_preference','Font Size Preference','UI font size preference.','Medium','Small,Medium,Large,XL','string','User'),('gdpr_mode','GDPR Enforcement Mode','Controls system behavior under GDPR rules.','Standard','Standard,Strict,Paranoid','string','System'),('login_alerts_enabled','Login Alerts Enabled','Notify when a login from a new device occurs.','On','On,Off','boolean','User'),('marketing_opt_in','Marketing Emails','Receive promotional communications.','No','Yes,No','boolean','User'),('max_nda_reminders','Max NDA Reminders (System Cap)','System-defined hard cap for NDA reminders.','3',NULL,'int','Hybrid'),('max_survey_reminders','Max Survey Reminders (System Cap)','System-defined hard cap for survey reminders.','3',NULL,'int','Hybrid'),('navigation_mode','Navigation Style','Sidebar or top navigation layout.','Sidebar','Sidebar,Top','string','User'),('participation_score_visibility','Participation Score Visibility','Show or hide user participation grades.','Hidden','Hidden,Visible','string','System'),('product_update_opt_in','Product Update Notifications','Receive product improvement updates.','Yes','Yes,No','boolean','User'),('security_notifications','Security Notifications','Receive alerts about suspicious activity.','On','On,Off','boolean','User'),('session_timeout','Session Timeout','Automatic logout time (minutes).','30',NULL,'int','User'),('survey_reminder_frequency','Survey Reminder Frequency','How often survey reminders are sent.','Daily','Immediate,Daily,Every3Days,Weekly,Off','string','User'),('theme_mode','Theme Mode','Light or Dark UI theme.','Light','Light,Dark,System','string','User'),('trial_update_notifications','Trial Update Notifications','Notify user when trial progresses.','On','On,Off','boolean','System');
/*!40000 ALTER TABLE `settings_definition` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `site_content_pages`
--

DROP TABLE IF EXISTS `site_content_pages`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `site_content_pages` (
  `PageID` varchar(50) NOT NULL,
  `Title` varchar(255) NOT NULL,
  `Slug` varchar(255) NOT NULL,
  `Content` text NOT NULL,
  `LastUpdatedAt` datetime NOT NULL,
  `LastUpdatedBy` varchar(100) NOT NULL,
  PRIMARY KEY (`PageID`),
  UNIQUE KEY `Slug` (`Slug`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `site_content_pages`
--

LOCK TABLES `site_content_pages` WRITE;
/*!40000 ALTER TABLE `site_content_pages` DISABLE KEYS */;
INSERT INTO `site_content_pages` VALUES ('guest_about_ut','About User Trials','about-user-trials','User Trials have existed at Logitech in various forms since the company’s earliest days.\n\nFrom the beginning, we have recognized that real-world usage ultimately defines how a product is experienced — often in ways that differ from initial design intent.\n\nBecause of this, user feedback has always played a critical role in shaping our products alongside internal innovation and design expertise.\n\nIn 2020, Logitech consolidated user testing efforts across individual teams and departments into a single, consistent User Trials program. This consolidation created a unified approach to recruiting, testing, and evaluating feedback across products.\n\nToday, User Trials allow Logitech to view new product introductions through a consistent and unbiased lens, helping identify where design intent and real-world usage align — and where they differ.\n\nIn many cases, the differences are minimal, or nonexistent. When that happens, it is a strong signal that the product is meeting user needs as intended.','2025-12-22 06:32:55','system_poc'),('guest_contact','Contact Us','contact-us','If you have general questions about the User Trials program, you may contact the team using the information below.\r\n\r\nPlease note that individual trial updates are not provided outside of the system unless additional information is required. {{CONTACT_FORM}}','2025-12-22 06:32:55','system_poc'),('guest_faq','Frequently Asked Questions','faq','\r\n<h3>How do I participate in a User Trial?</h3>\r\n<p>You must register and sign a non-disclosure agreement (NDA). Eligibility varies by trial.</p>\r\n\r\n<h3>Does registering guarantee participation?</h3>\r\n<p>No. Registration allows you to be considered for trials, but selection depends on specific research needs.</p>\r\n\r\n<h3>How are participants selected?</h3>\r\n<p>Participants are selected based on trial-specific criteria to ensure relevant and reliable feedback.</p>\r\n\r\n<h3>Why haven’t I heard back after registering or applying?</h3>\r\n<p>Not all trials require updates between selection and product shipment. If no updates are visible, it means the trial status has not changed.</p>\r\n\r\n<h3>Can I share information about a trial?</h3>\r\n<p>No. All trial information is confidential and subject to the NDA.</p>\r\n\r\n<h3>How often do trials run?</h3>\r\n<p>Trial frequency varies based on research needs and product timelines.</p>\r\n\r\n<h3>Why wasn’t I selected?</h3>\r\n<p>Selection is highly competitive, with many applicants for a limited number of spots. Decisions are based primarily on how well your profile matches the needs of a specific trial. In some cases, when multiple candidates are equally qualified, selection may be randomized. Providing thoughtful responses to optional questions can help strengthen your application.</p>\r\n\r\n<h3>I was recruited months ago, but the trial still hasn’t started. Was I removed?</h3>\r\n<p>No. If you are removed from a trial, you will always be notified and given a reason. Delays can happen due to scheduling or product readiness. Communication typically resumes when devices are ready to ship, including tracking details.</p>\r\n\r\n<h3>Will missing a survey affect my chances of being selected in the future?</h3>\r\n<p>Missing a few surveys will not automatically disqualify you. We understand participation is not your primary responsibility. However, consistent non-participation or lack of feedback over time may affect future selection decisions.</p>\r\n\r\n<h3>Will I receive any incentives for participating?</h3>\r\n<p>In most cases, participants are allowed to keep the trialed device. Occasionally, additional gestures such as gift cards may be provided. The program is designed for genuine engagement and feedback, not incentive-driven participation.</p>\r\n\r\n<h3>Why aren’t there assigned tasks during trials?</h3>\r\n<p>User trials are designed to observe natural product usage. Unlike structured user testing, there are typically no required tasks. You are encouraged to use the product as you normally would. Feedback is collected based on real-world experience.</p>\r\n\r\n<h3>Why is there limited interaction with the User Trials team?</h3>\r\n<p>Communication is focused on essential updates such as shipping details or setup guidance. However, the team is available if you reach out with questions or issues.</p>\r\n\r\n<h3>Can I see the results of a trial I participated in?</h3>\r\n<p>Yes. Results are generally made available after the trial concludes.</p>\r\n\r\n<h3>What can I do to improve my chances of being selected?</h3>\r\n<p>Provide honest and complete information in your application. A strong profile match is the most important factor. Applying to multiple trials can also improve your chances over time.</p>\r\n\r\n<h3>How do I know if two trials are happening at the same time?</h3>\r\n<p>Trials are considered concurrent if their recruitment periods overlap. While timelines may shift, we generally try to avoid placing users in multiple trials at the same time. If overlap does occur, you are welcome to participate in both.</p>\r\n\r\n<h3>What’s the difference between User Trials and Experience Testing?</h3>\r\n<p>Experience Testing typically involves structured sessions with assigned tasks and direct observation. User Trials involve a larger group of participants and focus on natural, real-world usage over time. Both approaches provide valuable but different types of feedback.</p>\r\n','2026-03-17 11:05:30','admin_tone_revision'),('guest_how_it_works','How User Trials Work','how-user-trials-work','User Trials are conducted in multiple stages to ensure consistency, confidentiality, and meaningful feedback.\n\nWhile each trial may differ based on product needs, the general process includes:\n\n1. Trial Planning\nResearch goals and participant requirements are defined internally.\n\n2. Participant Selection\nEligible users may be invited or allowed to apply based on trial criteria.\n\n3. Product Usage Period\nParticipants use the product in real-world conditions over a defined period.\n\n4. Feedback Collection\nFeedback is collected through structured surveys and open-ended responses.\n\n5. Analysis and Reporting\nResponses are anonymized, analyzed, and shared with relevant teams.\n\nNot all users will qualify for every trial, and participation is subject to availability and specific trial requirements.','2025-12-22 06:32:55','system_poc'),('guest_mission','Our Mission','our-mission','The User Trials program exists to ensure that real-world usage is represented alongside design, engineering, and innovation throughout the product development process.\n\nOur mission is to collect structured, unbiased feedback from users in authentic environments, helping teams understand how products are actually used — not just how they are intended to be used.\n\nBy maintaining a consistent and centralized approach to user trials, we aim to:\n\n- Reduce blind spots across teams and product categories\n- Ensure feedback is comparable across studies\n- Support better decision-making through reliable user insight\n\nUser Trials are not designed to replace internal expertise, but to complement it by grounding decisions in real user experience.','2025-12-22 06:32:55','system_poc'),('user_participation_guidelines','User Trial Participation Guidelines','participation-guidelines','## User Trial Participation Guidelines\r\n\r\nWe’re excited to have you join our User Trials program.\r\nOur goal is to create an open, reliable, and respectful testing community where your feedback genuinely influences our products.\r\nTo keep this process fair for everyone, we follow the guidelines below.\r\n\r\n## 1. General Expectations\r\n\r\n- Be responsive and reliable  \r\n  Reply promptly when contacted about onboarding, NDAs, shipping, or surveys.\r\n\r\n- Be thoughtful  \r\n  Share your honest experiences. Optional comments are your chance to explain why something worked or didn’t — that insight helps most.\r\n\r\n- Be respectful  \r\n  Interact professionally with Logitech staff and other participants.\r\n\r\n- Protect confidentiality  \r\n  All trial information is private unless otherwise stated.\r\n\r\n## 2. Communication & Reminders\r\n\r\nWe aim to keep reminders minimal.\r\n\r\nIf more than two personal reminders are required (for NDA signing, survey completion, or device return), your participation record may be marked as incomplete.\r\n\r\nConsistent follow-through helps maintain eligibility for future trials.\r\n\r\n## 3. NDA and Confidentiality\r\nEvery project will require a project specific NDA. All project NDAs must be signed and correctly submitted before participation can begin.\r\n\r\nFailure to sign or misrouting your NDA may delay or cancel participation.\r\n\r\nSharing or posting confidential product details, photos, or files will result in immediate removal from all current and future trials.\r\n\r\n## 4. Surveys and Feedback Quality\r\n\r\nYour feedback drives product decisions.\r\nPlease complete all required questions and provide comments where possible.\r\n\r\nExamples of poor-quality feedback that may affect eligibility include:\r\n- Leaving all open comment fields blank\r\n- Writing the same short response for every question\r\n- Copying and pasting identical text across unrelated sections\r\n\r\nNot every topic will inspire a long response — that’s okay.\r\nWe ask only that you contribute thoughtful input where you have relevant experience or opinions.\r\n\r\n## 5. Sample Handling\r\n\r\nAll samples remain company property unless otherwise stated.\r\n\r\nIf you cannot complete a trial, notify us and arrange a return.\r\n\r\nDamaged, lost, or unreturned devices may affect eligibility for future programs.\r\nIntentional misuse or failure to return a device will result in permanent exclusion.\r\n\r\n## 6. Conduct\r\n\r\nInappropriate, abusive, or unprofessional behavior toward staff or other participants will result in permanent removal from the program.\r\n\r\nWe are committed to maintaining a safe and respectful testing environment.\r\n\r\n## 7. Consequences and Eligibility\r\n\r\nParticipation history is tracked to ensure fair access to trials.\r\n\r\nDepending on context and history, consequences may include temporary suspension or permanent removal.\r\n\r\nFinal decisions are made by the User Trials team based on the full participation record.\r\n\r\n## 8. Positive Participation\r\n\r\nWe recognize and value great testers.\r\n\r\nConsistent, thoughtful, and timely participation may lead to:\r\n- Priority selection for future trials\r\n- Invitations to early or limited programs\r\n\r\nThank you for the time and care you bring to our trials.\r\nYour feedback helps shape better experiences for users worldwide.','2025-12-29 06:39:12','system_poc');
/*!40000 ALTER TABLE `site_content_pages` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `site_legal_documents`
--

DROP TABLE IF EXISTS `site_legal_documents`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `site_legal_documents` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `document_type` enum('privacy_statement','trial_participation_disclaimer','trial_participation_terms','data_usage_disclaimer','data_handling','cookie_notice','terms_of_service','accessibility_statement','nda') NOT NULL,
  `title` varchar(255) NOT NULL,
  `content` longtext NOT NULL,
  `version` varchar(50) NOT NULL,
  `status` enum('draft','active','archived') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'draft',
  `effective_date` datetime NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by_user_id` varchar(32) NOT NULL,
  `supersedes_id` bigint unsigned DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_doc_version` (`document_type`,`version`),
  KEY `fk_legal_created_by` (`created_by_user_id`),
  KEY `idx_legal_type_status` (`document_type`,`status`),
  KEY `idx_legal_effective_date` (`document_type`,`effective_date`),
  KEY `idx_legal_supersedes` (`supersedes_id`),
  CONSTRAINT `fk_legal_supersedes` FOREIGN KEY (`supersedes_id`) REFERENCES `site_legal_documents` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `site_legal_documents`
--

LOCK TABLES `site_legal_documents` WRITE;
/*!40000 ALTER TABLE `site_legal_documents` DISABLE KEYS */;
INSERT INTO `site_legal_documents` VALUES (1,'privacy_statement','Logitech User Trials Privacy Statement','\r\n<h2>1. Introduction</h2>\r\n\r\n<p>\r\nThis Privacy Statement explains how Logitech (“we”, “us”, or “our”) collects,\r\nuses, stores, and protects personal information through the Logitech User Trials\r\nwebsite (the “Site”).\r\n</p>\r\n\r\n<p>\r\nThis Site is operated for the sole purpose of managing participation in Logitech\r\nproduct user trials and research programs. It does not replace or supersede\r\nLogitech’s global Privacy Policy, which continues to apply where relevant.\r\n</p>\r\n\r\n<h2>2. Information We Collect</h2>\r\n\r\n<p>\r\nDepending on your participation, we may collect the following information:\r\n</p>\r\n\r\n<h3>Account Information</h3>\r\n<ul>\r\n    <li>Email address</li>\r\n    <li>Password (stored as a secure hash)</li>\r\n    <li>Account status and onboarding progress</li>\r\n</ul>\r\n\r\n<h3>Demographic Information</h3>\r\n<ul>\r\n    <li>First and last name</li>\r\n    <li>Gender</li>\r\n    <li>Birth year</li>\r\n    <li>Country and city of residence</li>\r\n</ul>\r\n\r\n<h3>Contact & Logistics Information</h3>\r\n<ul>\r\n    <li>Phone number</li>\r\n    <li>Shipping address (when required for trial participation)</li>\r\n</ul>\r\n\r\n<h3>Trial Participation Data</h3>\r\n<ul>\r\n    <li>Trial eligibility and selection status</li>\r\n    <li>NDA acknowledgements and timestamps</li>\r\n    <li>Survey responses and feedback</li>\r\n    <li>Participation history and scoring</li>\r\n</ul>\r\n\r\n<p>\r\nWe only collect information that is necessary to administer user trials and\r\nresearch activities.\r\n</p>\r\n\r\n<h2>3. How We Use Your Information</h2>\r\n\r\n<p>\r\nWe use your information to:\r\n</p>\r\n\r\n<ul>\r\n    <li>Determine eligibility for user trials</li>\r\n    <li>Communicate about trials and participation requirements</li>\r\n    <li>Manage NDAs and legal acknowledgements</li>\r\n    <li>Ship trial products where applicable</li>\r\n    <li>Collect feedback to improve Logitech products</li>\r\n    <li>Maintain internal records of participation and performance</li>\r\n</ul>\r\n\r\n<p>\r\nWe do not use User Trials data for advertising or marketing purposes unrelated\r\nto product research.\r\n</p>\r\n\r\n<h2>4. Legal Basis for Processing</h2>\r\n\r\n<p>\r\nWhere applicable, we process your personal information based on:\r\n</p>\r\n\r\n<ul>\r\n    <li>Your consent</li>\r\n    <li>Performance of a contract (trial participation)</li>\r\n    <li>Legitimate business interests related to product research</li>\r\n</ul>\r\n','1.0','active','2026-01-11 00:00:00','2026-01-11 04:49:32','userid_4fec82c7eea61',NULL),(2,'trial_participation_terms','Logitech User Trials – Trial Participation Terms','\r\n<h2>1. Purpose of User Trials</h2>\r\n\r\n<p>\r\nLogitech User Trials are conducted to evaluate products, features, and user\r\nexperiences prior to commercial release. Participation is voluntary and subject\r\nto eligibility requirements determined by Logitech.\r\n</p>\r\n\r\n<h2>2. Eligibility and Selection</h2>\r\n\r\n<p>\r\nSubmission of an application or completion of onboarding does not guarantee\r\nselection for a user trial. Logitech reserves the right to select, reject, or\r\nremove participants at its sole discretion.\r\n</p>\r\n\r\n<h2>3. Participant Responsibilities</h2>\r\n\r\n<p>\r\nIf selected, participants agree to:\r\n</p>\r\n\r\n<ul>\r\n    <li>Use trial products in accordance with provided instructions</li>\r\n    <li>Complete required surveys or feedback requests in a timely manner</li>\r\n    <li>Refrain from sharing confidential information or materials</li>\r\n    <li>Return trial products when requested, if applicable</li>\r\n</ul>\r\n\r\n<h2>4. Confidentiality and NDA</h2>\r\n\r\n<p>\r\nParticipation may require acceptance of a Non-Disclosure Agreement (NDA).\r\nFailure to comply with confidentiality obligations may result in removal from\r\nthe trial and exclusion from future trials.\r\n</p>\r\n\r\n<h2>5. Product Handling and Liability</h2>\r\n\r\n<p>\r\nTrial products may be pre-production and provided “as is.” Logitech is not\r\nresponsible for damages arising from use of trial products, except where\r\nrequired by applicable law.\r\n</p>\r\n\r\n<h2>6. Feedback and Usage Data</h2>\r\n\r\n<p>\r\nBy participating, you grant Logitech permission to collect and use feedback,\r\nusage data, and survey responses for research and product improvement purposes.\r\n</p>\r\n\r\n<h2>7. Termination of Participation</h2>\r\n\r\n<p>\r\nLogitech reserves the right to terminate participation at any time for any\r\nreason, including non-compliance with these terms.\r\n</p>\r\n\r\n<h2>8. Changes to These Terms</h2>\r\n\r\n<p>\r\nThese Trial Participation Terms may be updated from time to time. Continued\r\nparticipation after an update constitutes acceptance of the revised terms.\r\n</p>\r\n','1.0','active','2026-01-11 00:00:00','2026-01-11 05:35:59','userid_4fec82c7eea61',NULL),(3,'data_handling','Logitech User Trials – Data Handling Statement','\r\n<h2>1. Purpose of Data Handling</h2>\r\n\r\n<p>\r\nThis Data Handling Statement describes how personal data collected through the\r\nLogitech User Trials website is stored, processed, accessed, and retained for\r\nthe purpose of managing user trial participation.\r\n</p>\r\n\r\n<h2>2. Data Storage and Security</h2>\r\n\r\n<p>\r\nPersonal data collected through the User Trials platform is stored in secure\r\nsystems with access restricted to authorized personnel only. Logitech applies\r\nappropriate technical and organizational measures to protect personal data\r\nagainst unauthorized access, loss, or misuse.\r\n</p>\r\n\r\n<h2>3. Access Controls</h2>\r\n\r\n<p>\r\nAccess to personal data is granted on a role-based basis. Only individuals who\r\nrequire access to perform trial administration, logistics, legal review, or\r\nanalysis functions are permitted to view or modify data.\r\n</p>\r\n\r\n<h2>4. Data Retention</h2>\r\n\r\n<p>\r\nPersonal data is retained only for as long as necessary to fulfill the purposes\r\nof user trial management, comply with legal obligations, or resolve disputes.\r\nRetention periods may vary depending on the nature of the data and applicable\r\nregulatory requirements.\r\n</p>\r\n\r\n<h2>5. Data Sharing</h2>\r\n\r\n<p>\r\nPersonal data may be shared internally within Logitech for the purposes of\r\nproduct research, logistics, and compliance. Data is not shared with external\r\nthird parties except where necessary to fulfill trial operations (such as\r\nshipping providers) or where required by law.\r\n</p>\r\n\r\n<h2>6. International Data Transfers</h2>\r\n\r\n<p>\r\nUser Trials data may be processed or accessed in countries other than the\r\nparticipant’s country of residence. Where applicable, Logitech ensures\r\nappropriate safeguards are in place to protect personal data during such\r\ntransfers.\r\n</p>\r\n\r\n<h2>7. Participant Rights</h2>\r\n\r\n<p>\r\nParticipants may request access to, correction of, or deletion of their personal\r\ndata, subject to applicable laws and internal retention requirements.\r\n</p>\r\n\r\n<h2>8. Changes to This Statement</h2>\r\n\r\n<p>\r\nThis Data Handling Statement may be updated periodically. The version and\r\neffective date displayed on this page indicate the currently active version.\r\n</p>\r\n','1.0','active','2026-01-11 00:00:00','2026-01-11 05:37:11','userid_4fec82c7eea61',NULL),(4,'terms_of_service','Logitech User Trials – Terms of Service','\r\n<h2>1. Acceptance of Terms</h2>\r\n\r\n<p>\r\nBy accessing or using the Logitech User Trials website (the “Site”), you agree to\r\nbe bound by these Terms of Service. If you do not agree to these terms, you should\r\nnot use the Site or participate in user trials.\r\n</p>\r\n\r\n<h2>2. Scope of the Service</h2>\r\n\r\n<p>\r\nThe Site is provided for the purpose of managing participation in Logitech user\r\ntrials and research programs. The Site does not constitute a consumer-facing\r\ncommerce platform and does not offer products for sale.\r\n</p>\r\n\r\n<h2>3. Account Registration and Access</h2>\r\n\r\n<p>\r\nUsers may be required to register an account to access certain features of the\r\nSite. You are responsible for maintaining the confidentiality of your account\r\ncredentials and for all activity that occurs under your account.\r\n</p>\r\n\r\n<p>\r\nLogitech reserves the right to suspend or terminate accounts that violate these\r\nTerms or misuse the Site.\r\n</p>\r\n\r\n<h2>4. User Conduct</h2>\r\n\r\n<p>\r\nYou agree not to:\r\n</p>\r\n\r\n<ul>\r\n    <li>Provide false or misleading information</li>\r\n    <li>Attempt to gain unauthorized access to the Site or its systems</li>\r\n    <li>Interfere with the operation or security of the Site</li>\r\n    <li>Use the Site for purposes unrelated to authorized user trials</li>\r\n</ul>\r\n\r\n<h2>5. Intellectual Property</h2>\r\n\r\n<p>\r\nAll content, trademarks, and materials on the Site are owned by or licensed to\r\nLogitech. Use of the Site does not grant you any ownership or intellectual\r\nproperty rights.\r\n</p>\r\n\r\n<h2>6. Disclaimers</h2>\r\n\r\n<p>\r\nThe Site is provided on an “as is” and “as available” basis. Logitech makes no\r\nwarranties regarding availability, accuracy, or uninterrupted operation of the\r\nSite.\r\n</p>\r\n\r\n<h2>7. Limitation of Liability</h2>\r\n\r\n<p>\r\nTo the maximum extent permitted by law, Logitech shall not be liable for any\r\nindirect, incidental, or consequential damages arising out of or related to use\r\nof the Site.\r\n</p>\r\n\r\n<h2>8. Modifications to the Service or Terms</h2>\r\n\r\n<p>\r\nLogitech may modify these Terms of Service at any time. Updated terms will be\r\neffective as of the date indicated. Continued use of the Site constitutes\r\nacceptance of the revised terms.\r\n</p>\r\n\r\n<h2>9. Governing Law</h2>\r\n\r\n<p>\r\nThese Terms of Service are governed by and construed in accordance with\r\napplicable laws, without regard to conflict of law principles.\r\n</p>\r\n','1.0','active','2026-01-11 00:00:00','2026-01-11 05:38:18','userid_4fec82c7eea61',NULL),(5,'accessibility_statement','Logitech User Trials – Accessibility Statement','\r\n<h2>1. Commitment to Accessibility</h2>\r\n\r\n<p>\r\nLogitech is committed to ensuring digital accessibility for all users, including\r\nindividuals with disabilities. We strive to improve the user experience for\r\neveryone and to apply relevant accessibility standards to the Logitech User\r\nTrials website.\r\n</p>\r\n\r\n<h2>2. Accessibility Standards</h2>\r\n\r\n<p>\r\nThe User Trials website is designed with consideration for accessibility best\r\npractices and aims to conform, where feasible, to applicable accessibility\r\nguidelines such as the Web Content Accessibility Guidelines (WCAG).\r\n</p>\r\n\r\n<h2>3. Accessibility Features</h2>\r\n\r\n<p>\r\nAccessibility considerations may include:\r\n</p>\r\n\r\n<ul>\r\n    <li>Semantic HTML structure for improved screen reader compatibility</li>\r\n    <li>Keyboard-navigable interactive elements</li>\r\n    <li>Readable text contrast and scalable layouts</li>\r\n    <li>Clear and consistent navigation patterns</li>\r\n</ul>\r\n\r\n<h2>4. Limitations</h2>\r\n\r\n<p>\r\nWhile we make reasonable efforts to ensure accessibility, some content or\r\nfeatures may not yet be fully accessible due to technical constraints or ongoing\r\ndevelopment. Accessibility improvements are addressed as part of continuous\r\nsite enhancements.\r\n</p>\r\n\r\n<h2>5. Feedback and Assistance</h2>\r\n\r\n<p>\r\nIf you encounter accessibility barriers while using the User Trials website or\r\nrequire assistance, please contact us through the provided support or contact\r\nchannels. Feedback helps us identify areas for improvement.\r\n</p>\r\n\r\n<h2>6. Updates to This Statement</h2>\r\n\r\n<p>\r\nThis Accessibility Statement may be updated periodically to reflect improvements\r\nor changes to accessibility practices. The version and effective date displayed\r\non this page indicate the currently active version.\r\n</p>\r\n','1.0','active','2026-01-11 00:00:00','2026-01-11 05:38:48','userid_4fec82c7eea61',NULL),(6,'nda','Global Non-Disclosure Agreement','<p class=\"MsoNormal\"><strong>GLOBAL NON-DISCLOSURE AGREEMENT</strong></p>\n<p class=\"MsoNormal\">This Global Non-Disclosure Agreement (&ldquo;Agreement&rdquo;) is entered into between the participant (&ldquo;Participant&rdquo;) and the Company (&ldquo;Company&rdquo; or &ldquo;Logitech&rdquo;) as of the Effective Date listed below.</p>\n<p class=\"MsoNormal\"><strong>1. PURPOSE</strong></p>\n<p class=\"MsoNormal\">The purpose of this Agreement is to allow the Participant to access the Company&rsquo;s user trial platform, communications, and related materials for the limited purpose of evaluating, applying for, or participating in product research activities (&ldquo;Trials&rdquo;).</p>\n<p class=\"MsoNormal\"><strong>2. CONFIDENTIAL INFORMATION</strong></p>\n<p class=\"MsoNormal\">&ldquo;Confidential Information&rdquo; includes, but is not limited to:</p>\n<ul style=\"margin-top: 0in;\" type=\"disc\">\n<li class=\"MsoNormal\" style=\"mso-list: l5 level1 lfo1; tab-stops: list .5in;\">The existence of Trials</li>\n<li class=\"MsoNormal\" style=\"mso-list: l5 level1 lfo1; tab-stops: list .5in;\">Access to the user trial platform</li>\n<li class=\"MsoNormal\" style=\"mso-list: l5 level1 lfo1; tab-stops: list .5in;\">Pre-release products, software, services, or features</li>\n<li class=\"MsoNormal\" style=\"mso-list: l5 level1 lfo1; tab-stops: list .5in;\">Trial invitations, communications, instructions, and materials</li>\n<li class=\"MsoNormal\" style=\"mso-list: l5 level1 lfo1; tab-stops: list .5in;\">Any non-public information disclosed by the Company</li>\n</ul>\n<p class=\"MsoNormal\">Confidential Information does not include information that is publicly available through no fault of the Participant.</p>\n<p class=\"MsoNormal\"><strong>3. OBLIGATIONS OF PARTICIPANT</strong></p>\n<p class=\"MsoNormal\">The Participant agrees to:</p>\n<ul style=\"margin-top: 0in;\" type=\"disc\">\n<li class=\"MsoNormal\" style=\"mso-list: l1 level1 lfo2; tab-stops: list .5in;\">Keep all Confidential Information strictly confidential</li>\n<li class=\"MsoNormal\" style=\"mso-list: l1 level1 lfo2; tab-stops: list .5in;\">Not disclose, share, publish, or discuss Confidential Information with&nbsp;any third party</li>\n<li class=\"MsoNormal\" style=\"mso-list: l1 level1 lfo2; tab-stops: list .5in;\">Not publicly acknowledge participation in Trials unless explicitly&nbsp;permitted by the Company</li>\n<li class=\"MsoNormal\" style=\"mso-list: l1 level1 lfo2; tab-stops: list .5in;\">Use Confidential Information solely for purposes related to Trials</li>\n</ul>\n<p class=\"MsoNormal\"><strong>4. ACCESS AND PARTICIPATION</strong></p>\n<ul style=\"margin-top: 0in;\" type=\"disc\">\n<li class=\"MsoNormal\" style=\"mso-list: l6 level1 lfo3; tab-stops: list .5in;\">This Agreement does not guarantee selection for any Trial.<br>The Company may grant or revoke access to the platform or any Trial at its sole discretion.</li>\n</ul>\n<p class=\"MsoNormal\"><strong>5. OWNERSHIP</strong></p>\n<ul style=\"margin-top: 0in;\" type=\"disc\">\n<li class=\"MsoNormal\" style=\"mso-list: l4 level1 lfo4; tab-stops: list .5in;\">All Confidential Information remains the exclusive property of the Company.</li>\n<li class=\"MsoNormal\" style=\"mso-list: l4 level1 lfo4; tab-stops: list .5in;\">No license or ownership rights are granted under this Agreement.</li>\n</ul>\n<p class=\"MsoNormal\"><strong>6. DURATION</strong></p>\n<ul style=\"margin-top: 0in;\" type=\"disc\">\n<li class=\"MsoNormal\" style=\"mso-list: l0 level1 lfo5; tab-stops: list .5in;\">The obligations under this Agreement remain in effect until the&nbsp;Confidential Information becomes publicly available through authorized means or the Company provides written release.</li>\n</ul>\n<p class=\"MsoNormal\"><strong>7. NO OBLIGATION</strong></p>\n<ul style=\"margin-top: 0in;\" type=\"disc\">\n<li class=\"MsoNormal\" style=\"mso-list: l2 level1 lfo6; tab-stops: list .5in;\">Nothing in this Agreement obligates the Company to conduct any Trial or provide any compensation.</li>\n</ul>\n<p class=\"MsoNormal\"><strong>8. GOVERNING LAW</strong></p>\n<ul style=\"margin-top: 0in;\" type=\"disc\">\n<li class=\"MsoNormal\" style=\"mso-list: l3 level1 lfo7; tab-stops: list .5in;\">This Agreement is governed by the laws applicable to the Company&rsquo;s primary place of business, without regard to conflict-of-law principles.</li>\n<li class=\"MsoNormal\" style=\"mso-list: l3 level1 lfo7; tab-stops: list .5in;\">By accessing the platform or participating in any Trial, the Participant acknowledges that they have read, understood, and agree to this Agreement.</li>\n</ul>','1.0','archived','2026-01-20 07:43:23','2026-01-21 01:39:35','userid_4fec82c7eea61',NULL),(9,'nda','Global Non-Disclosure Agreement','<p class=\"MsoNormal\"><strong>GLOBAL NON-DISCLOSURE AGREEMENT</strong></p>\n<p class=\"MsoNormal\">This Global Non-Disclosure Agreement (&ldquo;Agreement&rdquo;) is entered into between the participant (&ldquo;Participant&rdquo;) and the Company (&ldquo;Company&rdquo; or &ldquo;Logitech&rdquo;) as of the Effective Date listed below.</p>\n<p class=\"MsoNormal\"><strong>1. PURPOSE OF AGREEMENT</strong></p>\n<p class=\"MsoNormal\">The purpose of this Agreement is to allow the Participant to access the Company&rsquo;s user trial platform, communications, and related materials for the limited purpose of evaluating, applying for, or participating in product research activities (&ldquo;Trials&rdquo;).</p>\n<p class=\"MsoNormal\"><strong>2. CONFIDENTIAL INFORMATION</strong></p>\n<p class=\"MsoNormal\">&ldquo;Confidential Information&rdquo; includes, but is not limited to:</p>\n<ul style=\"margin-top: 0in;\" type=\"disc\">\n<li class=\"MsoNormal\" style=\"mso-list: l5 level1 lfo1; tab-stops: list .5in;\">The existence of Trials (or User Trials)</li>\n<li class=\"MsoNormal\" style=\"mso-list: l5 level1 lfo1; tab-stops: list .5in;\">Access to the user trial platform</li>\n<li class=\"MsoNormal\" style=\"mso-list: l5 level1 lfo1; tab-stops: list .5in;\">Pre-release products, software, services, or features</li>\n<li class=\"MsoNormal\" style=\"mso-list: l5 level1 lfo1; tab-stops: list .5in;\">Trial invitations, communications, instructions, and materials</li>\n<li class=\"MsoNormal\" style=\"mso-list: l5 level1 lfo1; tab-stops: list .5in;\">Any non-public information disclosed by the Company</li>\n</ul>\n<p class=\"MsoNormal\">Confidential Information does not include information that is publicly available through no fault of the Participant.</p>\n<p class=\"MsoNormal\"><strong>3. OBLIGATIONS OF PARTICIPANT</strong></p>\n<p class=\"MsoNormal\">The Participant agrees to:</p>\n<ul style=\"margin-top: 0in;\" type=\"disc\">\n<li class=\"MsoNormal\" style=\"mso-list: l1 level1 lfo2; tab-stops: list .5in;\">Keep all Confidential Information strictly confidential</li>\n<li class=\"MsoNormal\" style=\"mso-list: l1 level1 lfo2; tab-stops: list .5in;\">Not disclose, share, publish, or discuss Confidential Information with&nbsp;any third party</li>\n<li class=\"MsoNormal\" style=\"mso-list: l1 level1 lfo2; tab-stops: list .5in;\">Not publicly acknowledge participation in Trials unless explicitly&nbsp;permitted by the Company</li>\n<li class=\"MsoNormal\" style=\"mso-list: l1 level1 lfo2; tab-stops: list .5in;\">Use Confidential Information solely for purposes related to Trials</li>\n</ul>\n<p class=\"MsoNormal\"><strong>4. ACCESS AND PARTICIPATION</strong></p>\n<ul style=\"margin-top: 0in;\" type=\"disc\">\n<li class=\"MsoNormal\" style=\"mso-list: l6 level1 lfo3; tab-stops: list .5in;\">This Agreement does not guarantee selection for any Trial.<br>The Company may grant or revoke access to the platform or any Trial at its sole discretion.</li>\n</ul>\n<p class=\"MsoNormal\"><strong>5. OWNERSHIP</strong></p>\n<ul style=\"margin-top: 0in;\" type=\"disc\">\n<li class=\"MsoNormal\" style=\"mso-list: l4 level1 lfo4; tab-stops: list .5in;\">All Confidential Information remains the exclusive property of the Company.</li>\n<li class=\"MsoNormal\" style=\"mso-list: l4 level1 lfo4; tab-stops: list .5in;\">No license or ownership rights are granted under this Agreement.</li>\n</ul>\n<p class=\"MsoNormal\"><strong>6. DURATION</strong></p>\n<ul style=\"margin-top: 0in;\" type=\"disc\">\n<li class=\"MsoNormal\" style=\"mso-list: l0 level1 lfo5; tab-stops: list .5in;\">The obligations under this Agreement remain in effect until the&nbsp;Confidential Information becomes publicly available through authorized means or the Company provides written release.</li>\n</ul>\n<p class=\"MsoNormal\"><strong>7. NO OBLIGATION</strong></p>\n<ul style=\"margin-top: 0in;\" type=\"disc\">\n<li class=\"MsoNormal\" style=\"mso-list: l2 level1 lfo6; tab-stops: list .5in;\">Nothing in this Agreement obligates the Company to conduct any Trial or provide any compensation.</li>\n</ul>\n<p class=\"MsoNormal\"><strong>8. GOVERNING LAW</strong></p>\n<ul style=\"margin-top: 0in;\" type=\"disc\">\n<li class=\"MsoNormal\" style=\"mso-list: l3 level1 lfo7; tab-stops: list .5in;\">This Agreement is governed by the laws applicable to the Company&rsquo;s primary place of business, without regard to conflict-of-law principles.</li>\n<li class=\"MsoNormal\" style=\"mso-list: l3 level1 lfo7; tab-stops: list .5in;\">By accessing the platform or participating in any Trial, the Participant acknowledges that they have read, understood, and agree to this Agreement.</li>\n</ul>','2.0','active','2026-01-21 10:43:23','2026-01-21 02:19:53','userid_4fec82c7eea61',6),(10,'terms_of_service','Logitech User Trials – Terms of Service','<h2>1. Acceptance of Terms</h2>\n<p>By accessing or using the Logitech User Trials website (the &ldquo;Site&rdquo;), you agree to be bound by these Terms of Service. If you do not agree to these terms, you should not use the Site or participate in user trials.</p>\n<h2>2. Scope of the Service</h2>\n<p>The Site is provided for the purpose of managing participation in Logitech user trials and research programs. The Site does not constitute a consumer-facing commerce platform and does not offer products for sale, nor does it commit to a garauntee of selection in a trial.</p>\n<h2>3. Account Registration and Access</h2>\n<p>Users may be required to register an account to access certain features of the Site. You are responsible for maintaining the confidentiality of your account credentials and for all activity that occurs under your account.</p>\n<p>Logitech reserves the right to suspend or terminate accounts that violate these Terms or misuse the Site.</p>\n<h2>4. User Conduct</h2>\n<p>You agree not to:</p>\n<ul>\n<li>Provide false or misleading information</li>\n<li>Attempt to gain unauthorized access to the Site or its systems</li>\n<li>Interfere with the operation or security of the Site</li>\n<li>Use the Site for purposes unrelated to authorized user trials</li>\n</ul>\n<h2>5. Intellectual Property</h2>\n<p>All content, trademarks, and materials on the Site are owned by or licensed to Logitech. Use of the Site does not grant you any ownership or intellectual property rights.</p>\n<h2>6. Disclaimers</h2>\n<p>The Site is provided on an &ldquo;as is&rdquo; and &ldquo;as available&rdquo; basis. Logitech makes no warranties regarding availability, accuracy, or uninterrupted operation of the Site.</p>\n<h2>7. Limitation of Liability</h2>\n<p>To the maximum extent permitted by law, Logitech shall not be liable for any indirect, incidental, or consequential damages arising out of or related to use of the Site.</p>\n<h2>8. Modifications to the Service or Terms</h2>\n<p>Logitech may modify these Terms of Service at any time. Updated terms will be effective as of the date indicated. Continued use of the Site constitutes acceptance of the revised terms.</p>\n<h2>9. Governing Law</h2>\n<p>These Terms of Service are governed by and construed in accordance with applicable laws, without regard to conflict of law principles.</p>','2.0','draft','2026-01-11 00:00:00','2026-01-21 02:46:49','userid_4fec82c7eea61',4);
/*!40000 ALTER TABLE `site_legal_documents` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `survey_answers`
--

DROP TABLE IF EXISTS `survey_answers`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `survey_answers` (
  `AnswerID` bigint unsigned NOT NULL AUTO_INCREMENT,
  `SurveyID` bigint unsigned NOT NULL,
  `DistributionID` bigint unsigned NOT NULL,
  `user_id` varchar(64) DEFAULT NULL,
  `ProjectID` varchar(64) NOT NULL,
  `RoundID` int NOT NULL,
  `SurveyTypeID` varchar(20) NOT NULL,
  `QuestionID` varchar(100) NOT NULL,
  `QuestionText` text,
  `AnswerValue` text,
  `AnswerNumeric` decimal(10,2) DEFAULT NULL,
  `SubmittedAt` datetime NOT NULL,
  `CreatedAt` datetime DEFAULT CURRENT_TIMESTAMP,
  `UpdatedAt` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`AnswerID`),
  KEY `idx_user` (`user_id`),
  KEY `idx_question` (`QuestionID`),
  KEY `idx_survey` (`SurveyID`),
  KEY `idx_project_round` (`ProjectID`,`RoundID`),
  KEY `fk_ans_distribution` (`DistributionID`),
  CONSTRAINT `fk_ans_distribution` FOREIGN KEY (`DistributionID`) REFERENCES `survey_distribution` (`DistributionID`) ON DELETE CASCADE,
  CONSTRAINT `fk_ans_survey` FOREIGN KEY (`SurveyID`) REFERENCES `survey_tracker` (`SurveyID`) ON DELETE CASCADE,
  CONSTRAINT `fk_ans_user` FOREIGN KEY (`user_id`) REFERENCES `user_pool` (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=1473 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `survey_answers`
--

LOCK TABLES `survey_answers` WRITE;
/*!40000 ALTER TABLE `survey_answers` DISABLE KEYS */;
INSERT INTO `survey_answers` VALUES (1449,26,40,'userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','Q_ab42293e29e1ffb3','Your name','asgsdg',NULL,'2026-03-30 16:18:36','2026-03-30 08:34:56','2026-03-30 08:34:56'),(1450,26,40,'userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','Q_bb0d5ba8438672f6','Read this carefully: Are you (if you are not a Logitech employee) and/or your family members currently employed (or potentially will be employed in the future) by or affiliated (or potentially will be affiliated in the future) or associated with any company that operates in the same or similar industry as ours or is a direct competitor in the gaming accessories and computer peripherals market?','No, I am OK to join this trial',NULL,'2026-03-30 16:18:36','2026-03-30 08:34:56','2026-03-30 08:34:56'),(1451,26,40,'userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','Q_cbe5cfcc20bf580e','What is your gender?','Male',NULL,'2026-03-30 16:18:36','2026-03-30 08:34:56','2026-03-30 08:34:56'),(1452,26,40,'userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','Q_cca57fe036393e59','What is your age range?','24 - 30',NULL,'2026-03-30 16:18:36','2026-03-30 08:34:56','2026-03-30 08:34:56'),(1453,26,40,'userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','Q_6cc545062202266f','Where are you located?','Germany',NULL,'2026-03-30 16:18:36','2026-03-30 08:34:56','2026-03-30 08:34:56'),(1454,26,40,'userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','Q_86710e60d0eae903','What is the Guardians full name?',NULL,NULL,'2026-03-30 16:18:36','2026-03-30 08:34:56','2026-03-30 08:34:56'),(1455,26,40,'userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','Q_5403e088f16b5336','What is the relationship to the minor participant?',NULL,NULL,'2026-03-30 16:18:36','2026-03-30 08:34:56','2026-03-30 08:34:56'),(1456,26,40,'userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','Q_7dc9a52606cd4d6b','Guardian\'s Email Address',NULL,NULL,'2026-03-30 16:18:36','2026-03-30 08:34:56','2026-03-30 08:34:56'),(1457,26,40,'userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','Q_5cc20a2e8833da0e','I confirm that I am the legal guardian of the minor named above. I have reviewed the description of the user trial, and I give my consent for their participation, including survey completion, product testing, and contact for logistics purposes.',NULL,NULL,'2026-03-30 16:18:36','2026-03-30 08:34:56','2026-03-30 08:34:56'),(1458,26,40,'userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','Q_0c33042230fb151e','Which best describes your experience with microphone setup and tuning?','I usually use default settings and only change things if something sounds wrong',NULL,'2026-03-30 16:18:36','2026-03-30 08:34:56','2026-03-30 08:34:56'),(1459,26,40,'userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','Q_43ef82445e266ec0','What activities do you anticipate using this microphone? (Select all that apply)','Streaming Content',NULL,'2026-03-30 16:18:36','2026-03-30 08:34:56','2026-03-30 08:34:56'),(1460,26,40,'userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','Q_41a633548f847077','You would classify yourself as which categories:',NULL,NULL,'2026-03-30 16:18:36','2026-03-30 08:34:56','2026-03-30 08:34:56'),(1461,26,40,'userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','Q_b4670d6a540d0e35','When something sounds “good enough,” how likely are you to keep adjusting settings?',NULL,NULL,'2026-03-30 16:18:36','2026-03-30 08:34:56','2026-03-30 08:34:56'),(1462,26,40,'userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','Q_af9571ed65b1d400','Which statement best matches your preference?','I don’t want to think about settings at all',NULL,'2026-03-30 16:18:36','2026-03-30 08:34:56','2026-03-30 08:34:56'),(1463,26,40,'userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','Q_b2f15e5b3bb2755f','How often do you use an external microphone?','3',3.00,'2026-03-30 16:18:36','2026-03-30 08:34:56','2026-03-30 08:34:56'),(1464,26,40,'userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','Q_b8a950f7e5d5f1d4','Optional Booster: In your own words, why would you like to join this trial?','I like Ice Cream',NULL,'2026-03-30 16:18:36','2026-03-30 08:34:56','2026-03-30 08:34:56'),(1465,26,40,'userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','Q_3180f726f16db55a','Are you able to come into the office to pick up your device, if selected? (For security reasons office pickups will be prioritized)','No',NULL,'2026-03-30 16:18:36','2026-03-30 08:34:56','2026-03-30 08:34:56'),(1466,26,40,'userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','Q_1a98ad5e40ff5d20','Are you sure you have a conflict of interest and cannot join this trial?',NULL,NULL,'2026-03-30 16:18:36','2026-03-30 08:34:56','2026-03-30 08:34:56'),(1467,26,40,'userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','Q_29e593abc059310e','If selected, which Logitech office would you prefer to collect the sample from?  (If you select Other, please give the full office address)',NULL,NULL,'2026-03-30 16:18:36','2026-03-30 08:34:56','2026-03-30 08:34:56'),(1468,26,40,'userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','Q_2b0418674dadd6ca','What is your contact number?',NULL,NULL,'2026-03-30 16:18:36','2026-03-30 08:34:56','2026-03-30 08:34:56'),(1469,26,40,'userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','Q_498680a1b8b4e0f8','Who will receive the device ( First and Last name)?','daf',NULL,'2026-03-30 16:18:36','2026-03-30 08:34:56','2026-03-30 08:34:56'),(1470,26,40,'userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','Q_95de6e837e4bd719','What is the recipient\'s contact number (with country code)?','asdg',NULL,'2026-03-30 16:18:36','2026-03-30 08:34:56','2026-03-30 08:34:56'),(1471,26,40,'userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','Q_6d53ded29592e3dd','What is the recipient\'s full shipping address (Including country name and Zip Code)?','asdg',NULL,'2026-03-30 16:18:36','2026-03-30 08:34:56','2026-03-30 08:34:56'),(1472,26,40,'userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','Q_c06397af4107458b','Here is the user Token:','69f2ccc9f9cb42a899ee47bf7e54e1bc',NULL,'2026-03-30 16:18:36','2026-03-30 08:34:56','2026-03-30 08:34:56');
/*!40000 ALTER TABLE `survey_answers` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `survey_distribution`
--

DROP TABLE IF EXISTS `survey_distribution`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `survey_distribution` (
  `DistributionID` bigint unsigned NOT NULL AUTO_INCREMENT,
  `SurveyID` bigint unsigned NOT NULL,
  `ProjectID` varchar(48) NOT NULL,
  `RoundID` int NOT NULL,
  `user_id` varchar(64) DEFAULT NULL,
  `SurveyTypeID` varchar(20) NOT NULL,
  `SentAt` datetime NOT NULL,
  `OpenedAt` datetime DEFAULT NULL,
  `CompletedAt` datetime DEFAULT NULL,
  `Deadline` datetime DEFAULT NULL,
  `ReminderCount` int unsigned DEFAULT '0',
  `LastReminderAt` datetime DEFAULT NULL,
  `Status` enum('not_sent','sent','opened','completed','late','dropped') DEFAULT 'sent',
  `CreatedAt` datetime DEFAULT CURRENT_TIMESTAMP,
  `UpdatedAt` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`DistributionID`),
  KEY `idx_survey_user` (`SurveyID`,`user_id`),
  KEY `idx_user` (`user_id`),
  KEY `idx_round` (`RoundID`),
  KEY `idx_survey_type` (`SurveyTypeID`),
  KEY `idx_status` (`Status`),
  KEY `fk_dist_project` (`ProjectID`),
  CONSTRAINT `fk_dist_project` FOREIGN KEY (`ProjectID`) REFERENCES `project_projects` (`ProjectID`) ON DELETE CASCADE,
  CONSTRAINT `fk_dist_round` FOREIGN KEY (`RoundID`) REFERENCES `project_rounds` (`RoundID`) ON DELETE CASCADE,
  CONSTRAINT `fk_dist_survey` FOREIGN KEY (`SurveyID`) REFERENCES `survey_tracker` (`SurveyID`) ON DELETE CASCADE,
  CONSTRAINT `fk_dist_type` FOREIGN KEY (`SurveyTypeID`) REFERENCES `survey_types` (`SurveyTypeID`) ON DELETE RESTRICT,
  CONSTRAINT `fk_dist_user` FOREIGN KEY (`user_id`) REFERENCES `user_pool` (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=41 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `survey_distribution`
--

LOCK TABLES `survey_distribution` WRITE;
/*!40000 ALTER TABLE `survey_distribution` DISABLE KEYS */;
INSERT INTO `survey_distribution` VALUES (40,26,'3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'userid_4fec82c7eea61','UTSurveyType0001','2026-03-30 16:18:36',NULL,'2026-03-30 16:18:36',NULL,0,NULL,'completed','2026-03-30 08:34:56','2026-03-30 08:34:56');
/*!40000 ALTER TABLE `survey_distribution` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `survey_participation_tokens`
--

DROP TABLE IF EXISTS `survey_participation_tokens`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `survey_participation_tokens` (
  `token_id` int NOT NULL AUTO_INCREMENT,
  `user_id` varchar(64) NOT NULL,
  `round_id` int NOT NULL,
  `survey_type` varchar(32) NOT NULL,
  `participation_token` varchar(64) NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `used_at` datetime DEFAULT NULL,
  PRIMARY KEY (`token_id`),
  UNIQUE KEY `participation_token` (`participation_token`),
  UNIQUE KEY `uniq_user_round_survey` (`user_id`,`round_id`,`survey_type`),
  KEY `idx_user_round` (`user_id`,`round_id`),
  KEY `idx_token` (`participation_token`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `survey_participation_tokens`
--

LOCK TABLES `survey_participation_tokens` WRITE;
/*!40000 ALTER TABLE `survey_participation_tokens` DISABLE KEYS */;
INSERT INTO `survey_participation_tokens` VALUES (1,'userid_4fec82c7eea61',26,'recruiting','69f2ccc9f9cb42a899ee47bf7e54e1bc','2026-03-28 10:23:58',NULL);
/*!40000 ALTER TABLE `survey_participation_tokens` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `survey_tracker`
--

DROP TABLE IF EXISTS `survey_tracker`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `survey_tracker` (
  `SurveyID` bigint unsigned NOT NULL AUTO_INCREMENT,
  `ProjectID` varchar(48) NOT NULL,
  `RoundID` int NOT NULL,
  `SurveyTypeID` varchar(20) NOT NULL,
  `SurveyTitle` varchar(255) DEFAULT NULL,
  `SurveyLink` text,
  `SurveyDate` datetime NOT NULL,
  `Status` enum('draft','scheduled','sent','in_progress','closed') DEFAULT 'draft',
  `ExpectedResponses` int unsigned DEFAULT NULL,
  `SurveyAdministrator` varchar(255) DEFAULT NULL,
  `CreatedAt` datetime DEFAULT CURRENT_TIMESTAMP,
  `UpdatedAt` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `IncludeInSnapshot` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`SurveyID`),
  KEY `idx_project_round` (`ProjectID`,`RoundID`),
  KEY `idx_survey_type` (`SurveyTypeID`),
  KEY `fk_tracker_round` (`RoundID`),
  CONSTRAINT `fk_tracker_project` FOREIGN KEY (`ProjectID`) REFERENCES `project_projects` (`ProjectID`) ON DELETE CASCADE,
  CONSTRAINT `fk_tracker_round` FOREIGN KEY (`RoundID`) REFERENCES `project_rounds` (`RoundID`) ON DELETE CASCADE,
  CONSTRAINT `fk_tracker_type` FOREIGN KEY (`SurveyTypeID`) REFERENCES `survey_types` (`SurveyTypeID`) ON DELETE RESTRICT
) ENGINE=InnoDB AUTO_INCREMENT=28 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `survey_tracker`
--

LOCK TABLES `survey_tracker` WRITE;
/*!40000 ALTER TABLE `survey_tracker` DISABLE KEYS */;
INSERT INTO `survey_tracker` VALUES (26,'3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001','TEST - Remo - User Trial Recruiting (Internal Only) (Responses) - Form Responses 1',NULL,'2026-03-30 08:34:56','closed',NULL,NULL,'2026-03-30 08:34:56','2026-03-30 08:34:56',1),(27,'a5ccb898-1d40-4bed-a890-b2849dcd0e88',27,'UTSurveyType0001','Repeater 1st Survey(OOBE and First Impressions) (Responses) - Form Responses 1',NULL,'2026-03-31 05:16:25','closed',NULL,NULL,'2026-03-31 05:16:24','2026-03-31 05:16:24',1);
/*!40000 ALTER TABLE `survey_tracker` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `survey_types`
--

DROP TABLE IF EXISTS `survey_types`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `survey_types` (
  `SurveyTypeID` varchar(20) NOT NULL,
  `SurveyTypeName` varchar(100) NOT NULL,
  `SurveyDescription` text,
  `CreatedAt` datetime DEFAULT CURRENT_TIMESTAMP,
  `UpdatedAt` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`SurveyTypeID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `survey_types`
--

LOCK TABLES `survey_types` WRITE;
/*!40000 ALTER TABLE `survey_types` DISABLE KEYS */;
INSERT INTO `survey_types` VALUES ('UTSurveyType0001','Recruiting','Survey used during the recruitment phase to gather potential candidates for trials.','2025-12-08 08:58:03','2025-12-08 08:58:03'),('UTSurveyType0002','Additional_Information','Collects extra details from participants, typically for profiling or segmentation.','2025-12-08 08:58:03','2025-12-08 08:58:03'),('UTSurveyType0009','FW_Update','Feedback after a firmware update, gauging the impact on user experience.','2025-12-08 08:58:03','2025-12-08 08:58:03'),('UTSurveyType0019','In_Person','In-person survey conducted during a physical trial or testing event.','2025-12-08 08:58:03','2025-12-08 08:58:03'),('UTSurveyType0027','Consolidated','Internal consolidated results file for Product Team review, combining insights across all surveys in the round.','2026-02-11 08:20:35','2026-02-11 08:20:35'),('UTSurveyType0028','Report_Issue','Always-on issue reporting survey for participants to submit bugs or defects during the trial.','2026-02-11 08:27:28','2026-02-11 08:27:28'),('UTSurveyType1001','Survey_1_OOBE_First_Impression','Primary early survey covering out-of-box experience and first impressions.','2026-03-15 05:36:22','2026-03-15 05:36:22'),('UTSurveyType1002','Survey_2_Experience_KPI','Primary experience survey capturing user experience, KPIs, and software usage.','2026-03-15 05:36:22','2026-03-15 05:36:22'),('UTSurveyType1003','Feature_Focus','Survey focused on specific product features.','2026-03-15 05:36:22','2026-03-15 05:36:22'),('UTSurveyType1004','Follow_Up','Follow-up survey requested during or after trial.','2026-03-15 05:36:22','2026-03-15 05:36:22'),('UTSurveyType1005','Final_Survey','Final survey capturing end-of-trial evaluation.','2026-03-15 05:36:22','2026-03-15 05:36:22');
/*!40000 ALTER TABLE `survey_types` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `survey_upload_audit`
--

DROP TABLE IF EXISTS `survey_upload_audit`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `survey_upload_audit` (
  `UploadID` bigint unsigned NOT NULL AUTO_INCREMENT,
  `FileHash` char(64) NOT NULL,
  `OriginalFilename` varchar(255) DEFAULT NULL,
  `UploadedByUserID` varchar(64) DEFAULT NULL,
  `ProjectID` varchar(64) DEFAULT NULL,
  `RoundID` int DEFAULT NULL,
  `SurveyTypeID` varchar(20) DEFAULT NULL,
  `SurveyID` bigint unsigned DEFAULT NULL,
  `InsertedAnswerRows` int unsigned DEFAULT NULL,
  `UploadedAt` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`UploadID`),
  UNIQUE KEY `uniq_filehash` (`FileHash`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `survey_upload_audit`
--

LOCK TABLES `survey_upload_audit` WRITE;
/*!40000 ALTER TABLE `survey_upload_audit` DISABLE KEYS */;
INSERT INTO `survey_upload_audit` VALUES (6,'0a06b88e1823e2683aa9c613f731a10beaa3e82443807311dce0cda63c4c9d53','TEST - Remo - User Trial Recruiting (Internal Only) (Responses) - Form Responses 1.csv','userid_4fec82c7eea61','3f2e7eb8-bd11-4d03-9919-af882becb0a8',26,'UTSurveyType0001',26,24,'2026-03-30 08:34:56'),(7,'68b014ad317e2b0aefd95dd5aac95fa481d5bd3ba541cb9e45d3f687bfb16d71','Repeater 1st Survey(OOBE and First Impressions) (Responses) - Form Responses 1.csv','userid_8a6a4e1d29a711f198b73a33889a1b82','a5ccb898-1d40-4bed-a890-b2849dcd0e88',27,'UTSurveyType0001',27,0,'2026-03-31 05:16:25');
/*!40000 ALTER TABLE `survey_upload_audit` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `system_office_locations`
--

DROP TABLE IF EXISTS `system_office_locations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `system_office_locations` (
  `OfficeID` varchar(20) NOT NULL,
  `OfficeName` varchar(255) DEFAULT NULL,
  `AddressLanguage` varchar(10) NOT NULL DEFAULT 'en',
  `AddressLine1` varchar(255) NOT NULL,
  `AddressLine2` varchar(255) DEFAULT NULL,
  `City` varchar(100) DEFAULT NULL,
  `StateRegion` varchar(100) DEFAULT NULL,
  `PostalCode` varchar(20) DEFAULT NULL,
  `Country` varchar(100) DEFAULT NULL,
  `IsActive` tinyint(1) NOT NULL DEFAULT '1',
  `CreatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `UpdatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`OfficeID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `system_office_locations`
--

LOCK TABLES `system_office_locations` WRITE;
/*!40000 ALTER TABLE `system_office_locations` DISABLE KEYS */;
INSERT INTO `system_office_locations` VALUES ('OFFICE_CH_LAUSANNE','BIC','en','EPFL Quartier de l\'Innovation','Logitech Europe SA','Lausanne',NULL,'1015','Switzerland',1,'2025-12-08 04:32:35','2025-12-08 04:32:35'),('OFFICE_CN_SHANGHAI','Logitech Shanghai Office','en','25F, Yueda 889, No.1111 Changshou Road','Jingan District','Shanghai',NULL,'200042','China',1,'2025-12-08 04:32:59','2025-12-08 04:32:59'),('OFFICE_CN_SUZHOU','Logitech Suzhou Tech Office','en','No. 3 Songsan Road, New District',NULL,'Suzhou','Jiangsu','215129','China',1,'2025-12-08 04:32:51','2025-12-08 04:32:51'),('OFFICE_DE_MUNICH','Logitech GmbH Munich','en','Prannerstrasse 8',NULL,'Munich','Bavaria','80333','Germany',1,'2025-12-08 04:34:32','2025-12-08 04:34:32'),('OFFICE_FR_PARIS','Logitech France','en','94 Rue de Villiers',NULL,'Levallois-Perret','Île-de-France','92300','France',1,'2025-12-08 04:33:49','2025-12-08 04:33:49'),('OFFICE_IE_CORK','Logitech Ireland','en','City Gate Plaza Two','Mahon','Cork',NULL,'T12 A6RW','Ireland',1,'2025-12-08 04:33:20','2025-12-08 04:33:20'),('OFFICE_IN_CHENNAI','Logitech Chennai','en','10th Floor, Fortius Block, Building 1, Olympia Technology Park','Warm Shell Basis, SIDCO Industrial Estate, Guindy','Chennai','Tamil Nadu','600032','India',1,'2025-12-08 04:33:35','2025-12-08 04:33:35'),('OFFICE_JP_TOKYO','Logicool Japan Office','en','Shiroyama Trust Tower 14F, 4-3-1 Toranomon','Minato-ku','Tokyo',NULL,'105-6014','Japan',1,'2025-12-08 04:33:42','2025-12-08 04:33:42'),('OFFICE_KR_SEOUL','Logitech Korea Office','en','402B CCMM Bldg, 12 Yeouido-dong, Yeongdeungpo-gu',NULL,'Seoul',NULL,'150-968','South Korea',1,'2025-12-08 04:34:19','2025-12-08 04:34:19'),('OFFICE_NL_UTRECHT','Logitech Utrecht Office','en','Catharijnesingel 47',NULL,'Utrecht',NULL,'3511 GC','Netherlands',1,'2025-12-08 04:32:44','2025-12-08 04:32:44'),('OFFICE_TW_HSINCHU','Logitech Hsinchu Office','en','No. 2, Yanxin 4th Rd, East District',NULL,'Hsinchu City',NULL,'300','Taiwan',1,'2025-12-08 04:32:17','2025-12-08 04:32:17'),('OFFICE_US_CAMAS','Logitech Camas Office','en','4700 NW Camas Meadows Dr.',NULL,'Camas','WA','98607','USA',1,'2025-12-08 04:32:01','2025-12-08 04:32:01'),('OFFICE_US_IRVINE','Logitech Irvine Office','en','3 Jenner #180',NULL,'Irvine','CA','92618','USA',1,'2025-12-08 04:32:09','2025-12-08 04:32:09'),('OFFICE_US_SJC','SVC','en','3930 North First St.',NULL,'San Jose','CA','95134','USA',1,'2025-12-08 04:31:54','2025-12-08 04:31:54');
/*!40000 ALTER TABLE `system_office_locations` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `system_settings`
--

DROP TABLE IF EXISTS `system_settings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `system_settings` (
  `SystemSettingID` int NOT NULL AUTO_INCREMENT,
  `SettingKey` varchar(100) NOT NULL,
  `SettingValue` varchar(255) DEFAULT NULL,
  `UpdatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`SystemSettingID`),
  UNIQUE KEY `uniq_system_setting` (`SettingKey`),
  CONSTRAINT `system_settings_ibfk_1` FOREIGN KEY (`SettingKey`) REFERENCES `settings_definition` (`SettingKey`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `system_settings`
--

LOCK TABLES `system_settings` WRITE;
/*!40000 ALTER TABLE `system_settings` DISABLE KEYS */;
INSERT INTO `system_settings` VALUES (1,'auto_blacklist_threshold','3','2025-12-08 03:16:52'),(2,'default_nda_reminder_limit','3','2025-12-08 03:16:52'),(3,'default_survey_reminder_limit','3','2025-12-08 03:16:52'),(4,'device_verification_required','Off','2025-12-08 03:16:52'),(5,'gdpr_mode','Standard','2025-12-08 03:16:52'),(6,'participation_score_visibility','Hidden','2025-12-08 03:16:52'),(7,'trial_update_notifications','On','2025-12-08 03:16:52'),(8,'max_nda_reminders','3','2025-12-08 03:16:52'),(9,'max_survey_reminders','3','2025-12-08 03:16:52');
/*!40000 ALTER TABLE `system_settings` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `trial_issue_messages`
--

DROP TABLE IF EXISTS `trial_issue_messages`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `trial_issue_messages` (
  `message_id` bigint NOT NULL AUTO_INCREMENT,
  `issue_id` bigint NOT NULL,
  `sender_role` enum('participant','internal') NOT NULL,
  `message_text` text NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`message_id`),
  KEY `idx_issue_created` (`issue_id`,`created_at`),
  CONSTRAINT `fk_issue_messages_issue` FOREIGN KEY (`issue_id`) REFERENCES `trial_issues` (`issue_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `trial_issue_messages`
--

LOCK TABLES `trial_issue_messages` WRITE;
/*!40000 ALTER TABLE `trial_issue_messages` DISABLE KEYS */;
/*!40000 ALTER TABLE `trial_issue_messages` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `trial_issues`
--

DROP TABLE IF EXISTS `trial_issues`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `trial_issues` (
  `issue_id` bigint NOT NULL AUTO_INCREMENT,
  `trial_round_id` int NOT NULL,
  `user_id` varchar(64) DEFAULT NULL,
  `nickname_trial` varchar(64) NOT NULL,
  `issue_category_user` varchar(64) NOT NULL,
  `severity_user` varchar(32) DEFAULT NULL,
  `summary` varchar(255) DEFAULT NULL,
  `description` text NOT NULL,
  `status` varchar(32) NOT NULL DEFAULT 'submitted',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `jira_key` varchar(32) DEFAULT NULL,
  `jira_url` varchar(255) DEFAULT NULL,
  `jira_synced_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`issue_id`),
  KEY `idx_trial_round` (`trial_round_id`),
  KEY `idx_user` (`user_id`),
  KEY `idx_status` (`status`),
  CONSTRAINT `fk_trial_issues_round` FOREIGN KEY (`trial_round_id`) REFERENCES `project_rounds` (`RoundID`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `trial_issues`
--

LOCK TABLES `trial_issues` WRITE;
/*!40000 ALTER TABLE `trial_issues` DISABLE KEYS */;
/*!40000 ALTER TABLE `trial_issues` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `user_blacklist`
--

DROP TABLE IF EXISTS `user_blacklist`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_blacklist` (
  `BlacklistID` int NOT NULL AUTO_INCREMENT,
  `BlacklistType` enum('email','domain') NOT NULL,
  `Email` varchar(255) DEFAULT NULL,
  `Domain` varchar(255) DEFAULT NULL,
  `UserID` int DEFAULT NULL,
  `ReasonCode` varchar(50) NOT NULL,
  `ReasonDetail` text,
  `IsActive` tinyint(1) NOT NULL DEFAULT '1',
  `CreatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `CreatedBy` int DEFAULT NULL,
  `ExpiresAt` datetime DEFAULT NULL,
  PRIMARY KEY (`BlacklistID`),
  KEY `idx_email_active` (`Email`,`IsActive`),
  KEY `idx_domain_active` (`Domain`,`IsActive`),
  KEY `idx_userid` (`UserID`),
  CONSTRAINT `user_blacklist_chk_1` CHECK ((((`BlacklistType` = _utf8mb4'email') and (`Email` is not null) and (`Domain` is null)) or ((`BlacklistType` = _utf8mb4'domain') and (`Domain` is not null) and (`Email` is null))))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user_blacklist`
--

LOCK TABLES `user_blacklist` WRITE;
/*!40000 ALTER TABLE `user_blacklist` DISABLE KEYS */;
/*!40000 ALTER TABLE `user_blacklist` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `user_home_address`
--

DROP TABLE IF EXISTS `user_home_address`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_home_address` (
  `HomeAddressID` int NOT NULL AUTO_INCREMENT,
  `user_id` varchar(64) DEFAULT NULL,
  `AddressLanguage` varchar(10) NOT NULL DEFAULT 'en',
  `AddressLine1` varchar(255) NOT NULL,
  `AddressLine2` varchar(255) DEFAULT NULL,
  `City` varchar(100) DEFAULT NULL,
  `StateRegion` varchar(100) DEFAULT NULL,
  `PostalCode` varchar(20) DEFAULT NULL,
  `Country` varchar(100) DEFAULT NULL,
  `IsDefault` tinyint(1) NOT NULL DEFAULT '0',
  `CreatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `UpdatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`HomeAddressID`),
  KEY `UserID` (`user_id`),
  CONSTRAINT `user_home_address_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user_pool` (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user_home_address`
--

LOCK TABLES `user_home_address` WRITE;
/*!40000 ALTER TABLE `user_home_address` DISABLE KEYS */;
/*!40000 ALTER TABLE `user_home_address` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `user_interest_map`
--

DROP TABLE IF EXISTS `user_interest_map`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_interest_map` (
  `InterestMapID` bigint NOT NULL AUTO_INCREMENT,
  `user_id` varchar(64) DEFAULT NULL,
  `InterestUID` varchar(20) NOT NULL,
  `CreatedAt` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`InterestMapID`),
  UNIQUE KEY `uq_user_interest` (`user_id`,`InterestUID`),
  KEY `idx_user_interest_user` (`user_id`),
  KEY `idx_user_interest_interest` (`InterestUID`),
  CONSTRAINT `fk_interest_map_interest` FOREIGN KEY (`InterestUID`) REFERENCES `user_interests` (`InterestUID`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1858 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user_interest_map`
--

LOCK TABLES `user_interest_map` WRITE;
/*!40000 ALTER TABLE `user_interest_map` DISABLE KEYS */;
INSERT INTO `user_interest_map` VALUES (1182,'userid_8c2a449ff5031','InterestUID_702a','2026-01-19 07:39:34'),(1183,'userid_8c2a449ff5031','InterestUID_702b','2026-01-19 07:39:34'),(1184,'userid_8c2a449ff5031','InterestUID_703a','2026-01-19 07:39:34'),(1185,'userid_8c2a449ff5031','InterestUID_703b','2026-01-19 07:39:34'),(1186,'userid_8c2a449ff5031','InterestUID_703c','2026-01-19 07:39:34'),(1187,'userid_8c2a449ff5031','InterestUID_703d','2026-01-19 07:39:34'),(1188,'userid_8c2a449ff5031','InterestUID_801a','2026-01-19 07:39:34'),(1189,'userid_8c2a449ff5031','InterestUID_801b','2026-01-19 07:39:34'),(1190,'userid_8c2a449ff5031','InterestUID_802a','2026-01-19 07:39:34'),(1191,'userid_8c2a449ff5031','InterestUID_802b','2026-01-19 07:39:34'),(1192,'userid_8c2a449ff5031','InterestUID_803a','2026-01-19 07:39:34'),(1193,'userid_8c2a449ff5031','InterestUID_803b','2026-01-19 07:39:34'),(1194,'userid_8c2a449ff5031','InterestUID_803c','2026-01-19 07:39:34'),(1195,'userid_8c2a449ff5031','InterestUID_901a','2026-01-19 07:39:34'),(1196,'userid_8c2a449ff5031','InterestUID_901b','2026-01-19 07:39:34'),(1197,'userid_8c2a449ff5031','InterestUID_901c','2026-01-19 07:39:34'),(1198,'userid_8c2a449ff5031','InterestUID_902a','2026-01-19 07:39:34'),(1199,'userid_8c2a449ff5031','InterestUID_902b','2026-01-19 07:39:34'),(1200,'userid_8c2a449ff5031','InterestUID_902c','2026-01-19 07:39:34'),(1201,'userid_8c2a449ff5031','InterestUID_301a','2026-01-19 07:39:34'),(1202,'userid_8c2a449ff5031','InterestUID_301b','2026-01-19 07:39:34'),(1203,'userid_8c2a449ff5031','InterestUID_301c','2026-01-19 07:39:34'),(1204,'userid_8c2a449ff5031','InterestUID_302a','2026-01-19 07:39:34'),(1205,'userid_8c2a449ff5031','InterestUID_302b','2026-01-19 07:39:34'),(1206,'userid_8c2a449ff5031','InterestUID_303a','2026-01-19 07:39:34'),(1207,'userid_8c2a449ff5031','InterestUID_303b','2026-01-19 07:39:34'),(1208,'userid_8c2a449ff5031','InterestUID_303c','2026-01-19 07:39:34'),(1209,'userid_8c2a449ff5031','InterestUID_201a','2026-01-19 07:39:34'),(1210,'userid_8c2a449ff5031','InterestUID_201b','2026-01-19 07:39:34'),(1211,'userid_8c2a449ff5031','InterestUID_202a','2026-01-19 07:39:34'),(1212,'userid_8c2a449ff5031','InterestUID_202b','2026-01-19 07:39:34'),(1213,'userid_8c2a449ff5031','InterestUID_203a','2026-01-19 07:39:34'),(1214,'userid_8c2a449ff5031','InterestUID_203b','2026-01-19 07:39:34'),(1215,'userid_8c2a449ff5031','InterestUID_203c','2026-01-19 07:39:34'),(1216,'userid_8c2a449ff5031','InterestUID_102a','2026-01-19 07:39:34'),(1217,'userid_8c2a449ff5031','InterestUID_102b','2026-01-19 07:39:34'),(1218,'userid_8c2a449ff5031','InterestUID_102c','2026-01-19 07:39:34'),(1219,'userid_8c2a449ff5031','InterestUID_102d','2026-01-19 07:39:34'),(1220,'userid_8c2a449ff5031','InterestUID_102e','2026-01-19 07:39:34'),(1221,'userid_8c2a449ff5031','InterestUID_102f','2026-01-19 07:39:34'),(1222,'userid_8c2a449ff5031','InterestUID_102g','2026-01-19 07:39:34'),(1223,'userid_8c2a449ff5031','InterestUID_102h','2026-01-19 07:39:34'),(1224,'userid_e12c2650f5b71','InterestUID_101a','2026-01-20 04:36:36'),(1225,'userid_e12c2650f5b71','InterestUID_101b','2026-01-20 04:36:36'),(1226,'userid_e12c2650f5b71','InterestUID_101c','2026-01-20 04:36:36'),(1227,'userid_e12c2650f5b71','InterestUID_101d','2026-01-20 04:36:36'),(1228,'userid_e12c2650f5b71','InterestUID_101e','2026-01-20 04:36:36'),(1229,'userid_e12c2650f5b71','InterestUID_101f','2026-01-20 04:36:36'),(1230,'userid_e12c2650f5b71','InterestUID_101g','2026-01-20 04:36:36'),(1231,'userid_e12c2650f5b71','InterestUID_103a','2026-01-20 04:36:36'),(1232,'userid_e12c2650f5b71','InterestUID_103b','2026-01-20 04:36:36'),(1233,'userid_e12c2650f5b71','InterestUID_103c','2026-01-20 04:36:36'),(1234,'userid_e12c2650f5b71','InterestUID_1001a','2026-01-20 04:36:36'),(1235,'userid_e12c2650f5b71','InterestUID_1001b','2026-01-20 04:36:36'),(1236,'userid_e12c2650f5b71','InterestUID_1001c','2026-01-20 04:36:36'),(1237,'userid_e12c2650f5b71','InterestUID_201a','2026-01-20 04:36:36'),(1238,'userid_e12c2650f5b71','InterestUID_201b','2026-01-20 04:36:36'),(1239,'userid_e12c2650f5b71','InterestUID_202a','2026-01-20 04:36:36'),(1240,'userid_e12c2650f5b71','InterestUID_202b','2026-01-20 04:36:36'),(1241,'userid_e12c2650f5b71','InterestUID_203a','2026-01-20 04:36:36'),(1242,'userid_e12c2650f5b71','InterestUID_203b','2026-01-20 04:36:36'),(1243,'userid_e12c2650f5b71','InterestUID_203c','2026-01-20 04:36:36'),(1244,'userid_e12c2650f5b71','InterestUID_301a','2026-01-20 04:36:36'),(1245,'userid_e12c2650f5b71','InterestUID_301b','2026-01-20 04:36:36'),(1246,'userid_e12c2650f5b71','InterestUID_301c','2026-01-20 04:36:36'),(1247,'userid_e12c2650f5b71','InterestUID_302a','2026-01-20 04:36:36'),(1248,'userid_e12c2650f5b71','InterestUID_302b','2026-01-20 04:36:36'),(1249,'userid_e12c2650f5b71','InterestUID_303a','2026-01-20 04:36:36'),(1250,'userid_e12c2650f5b71','InterestUID_303b','2026-01-20 04:36:36'),(1251,'userid_e12c2650f5b71','InterestUID_303c','2026-01-20 04:36:36'),(1252,'userid_e12c2650f5b71','InterestUID_401a','2026-01-20 04:36:36'),(1253,'userid_e12c2650f5b71','InterestUID_401b','2026-01-20 04:36:36'),(1254,'userid_e12c2650f5b71','InterestUID_402a','2026-01-20 04:36:36'),(1255,'userid_e12c2650f5b71','InterestUID_402b','2026-01-20 04:36:36'),(1256,'userid_e12c2650f5b71','InterestUID_402c','2026-01-20 04:36:36'),(1257,'userid_e12c2650f5b71','InterestUID_403a','2026-01-20 04:36:36'),(1258,'userid_e12c2650f5b71','InterestUID_403b','2026-01-20 04:36:36'),(1259,'userid_e12c2650f5b71','InterestUID_404a','2026-01-20 04:36:36'),(1260,'userid_e12c2650f5b71','InterestUID_404b','2026-01-20 04:36:36'),(1261,'userid_e12c2650f5b71','InterestUID_405a','2026-01-20 04:36:36'),(1262,'userid_e12c2650f5b71','InterestUID_405b','2026-01-20 04:36:36'),(1263,'userid_e12c2650f5b71','InterestUID_405c','2026-01-20 04:36:36'),(1264,'userid_e12c2650f5b71','InterestUID_501a','2026-01-20 04:36:36'),(1265,'userid_e12c2650f5b71','InterestUID_501b','2026-01-20 04:36:36'),(1266,'userid_e12c2650f5b71','InterestUID_502a','2026-01-20 04:36:36'),(1267,'userid_e12c2650f5b71','InterestUID_502b','2026-01-20 04:36:36'),(1268,'userid_e12c2650f5b71','InterestUID_503a','2026-01-20 04:36:36'),(1269,'userid_e12c2650f5b71','InterestUID_503b','2026-01-20 04:36:36'),(1270,'userid_e12c2650f5b71','InterestUID_901a','2026-01-20 04:36:36'),(1271,'userid_e12c2650f5b71','InterestUID_901b','2026-01-20 04:36:36'),(1272,'userid_e12c2650f5b71','InterestUID_901c','2026-01-20 04:36:36'),(1273,'userid_e12c2650f5b71','InterestUID_902a','2026-01-20 04:36:36'),(1274,'userid_e12c2650f5b71','InterestUID_902b','2026-01-20 04:36:36'),(1275,'userid_e12c2650f5b71','InterestUID_902c','2026-01-20 04:36:36'),(1276,'userid_e12c2650f5b71','InterestUID_801a','2026-01-20 04:36:36'),(1277,'userid_e12c2650f5b71','InterestUID_801b','2026-01-20 04:36:36'),(1278,'userid_e12c2650f5b71','InterestUID_802a','2026-01-20 04:36:36'),(1279,'userid_e12c2650f5b71','InterestUID_802b','2026-01-20 04:36:36'),(1280,'userid_e12c2650f5b71','InterestUID_803a','2026-01-20 04:36:36'),(1281,'userid_e12c2650f5b71','InterestUID_803b','2026-01-20 04:36:36'),(1282,'userid_e12c2650f5b71','InterestUID_803c','2026-01-20 04:36:36'),(1283,'userid_e12c2650f5b71','InterestUID_701a','2026-01-20 04:36:36'),(1284,'userid_e12c2650f5b71','InterestUID_701b','2026-01-20 04:36:36'),(1285,'userid_e12c2650f5b71','InterestUID_702a','2026-01-20 04:36:36'),(1286,'userid_e12c2650f5b71','InterestUID_702b','2026-01-20 04:36:36'),(1287,'userid_e12c2650f5b71','InterestUID_703a','2026-01-20 04:36:36'),(1288,'userid_e12c2650f5b71','InterestUID_703b','2026-01-20 04:36:36'),(1289,'userid_e12c2650f5b71','InterestUID_703c','2026-01-20 04:36:36'),(1290,'userid_e12c2650f5b71','InterestUID_703d','2026-01-20 04:36:36'),(1291,'userid_e12c2650f5b71','InterestUID_601a','2026-01-20 04:36:36'),(1292,'userid_e12c2650f5b71','InterestUID_601b','2026-01-20 04:36:36'),(1293,'userid_e12c2650f5b71','InterestUID_602a','2026-01-20 04:36:36'),(1294,'userid_e12c2650f5b71','InterestUID_602b','2026-01-20 04:36:36'),(1295,'userid_e12c2650f5b71','InterestUID_602c','2026-01-20 04:36:36'),(1296,'userid_e12c2650f5b71','InterestUID_603a','2026-01-20 04:36:36'),(1297,'userid_e12c2650f5b71','InterestUID_603b','2026-01-20 04:36:36'),(1298,'userid_e12c2650f5b71','InterestUID_603c','2026-01-20 04:36:36'),(1299,'userid_e12c2650f5b71','InterestUID_102a','2026-01-20 04:36:36'),(1300,'userid_e12c2650f5b71','InterestUID_102b','2026-01-20 04:36:36'),(1301,'userid_e12c2650f5b71','InterestUID_102c','2026-01-20 04:36:36'),(1302,'userid_e12c2650f5b71','InterestUID_102d','2026-01-20 04:36:36'),(1303,'userid_e12c2650f5b71','InterestUID_102e','2026-01-20 04:36:36'),(1304,'userid_e12c2650f5b71','InterestUID_102f','2026-01-20 04:36:36'),(1305,'userid_e12c2650f5b71','InterestUID_102g','2026-01-20 04:36:36'),(1306,'userid_e12c2650f5b71','InterestUID_102h','2026-01-20 04:36:36'),(1390,'userid_09eb7cc3ef8f1','InterestUID_101a','2026-01-20 07:12:30'),(1391,'userid_09eb7cc3ef8f1','InterestUID_101b','2026-01-20 07:12:30'),(1392,'userid_09eb7cc3ef8f1','InterestUID_101c','2026-01-20 07:12:30'),(1393,'userid_09eb7cc3ef8f1','InterestUID_101d','2026-01-20 07:12:30'),(1394,'userid_09eb7cc3ef8f1','InterestUID_101e','2026-01-20 07:12:30'),(1395,'userid_09eb7cc3ef8f1','InterestUID_101f','2026-01-20 07:12:30'),(1396,'userid_09eb7cc3ef8f1','InterestUID_101g','2026-01-20 07:12:30'),(1397,'userid_09eb7cc3ef8f1','InterestUID_103a','2026-01-20 07:12:30'),(1398,'userid_09eb7cc3ef8f1','InterestUID_103b','2026-01-20 07:12:30'),(1399,'userid_09eb7cc3ef8f1','InterestUID_103c','2026-01-20 07:12:30'),(1400,'userid_09eb7cc3ef8f1','InterestUID_1001a','2026-01-20 07:12:30'),(1401,'userid_09eb7cc3ef8f1','InterestUID_1001b','2026-01-20 07:12:30'),(1402,'userid_09eb7cc3ef8f1','InterestUID_1001c','2026-01-20 07:12:30'),(1403,'userid_09eb7cc3ef8f1','InterestUID_201a','2026-01-20 07:12:30'),(1404,'userid_09eb7cc3ef8f1','InterestUID_201b','2026-01-20 07:12:30'),(1405,'userid_09eb7cc3ef8f1','InterestUID_202a','2026-01-20 07:12:30'),(1406,'userid_09eb7cc3ef8f1','InterestUID_202b','2026-01-20 07:12:30'),(1407,'userid_09eb7cc3ef8f1','InterestUID_203a','2026-01-20 07:12:30'),(1408,'userid_09eb7cc3ef8f1','InterestUID_203b','2026-01-20 07:12:30'),(1409,'userid_09eb7cc3ef8f1','InterestUID_203c','2026-01-20 07:12:30'),(1410,'userid_09eb7cc3ef8f1','InterestUID_301a','2026-01-20 07:12:30'),(1411,'userid_09eb7cc3ef8f1','InterestUID_301b','2026-01-20 07:12:30'),(1412,'userid_09eb7cc3ef8f1','InterestUID_301c','2026-01-20 07:12:30'),(1413,'userid_09eb7cc3ef8f1','InterestUID_302a','2026-01-20 07:12:30'),(1414,'userid_09eb7cc3ef8f1','InterestUID_302b','2026-01-20 07:12:30'),(1415,'userid_09eb7cc3ef8f1','InterestUID_303a','2026-01-20 07:12:30'),(1416,'userid_09eb7cc3ef8f1','InterestUID_303b','2026-01-20 07:12:30'),(1417,'userid_09eb7cc3ef8f1','InterestUID_303c','2026-01-20 07:12:30'),(1418,'userid_09eb7cc3ef8f1','InterestUID_401a','2026-01-20 07:12:30'),(1419,'userid_09eb7cc3ef8f1','InterestUID_401b','2026-01-20 07:12:30'),(1420,'userid_09eb7cc3ef8f1','InterestUID_402a','2026-01-20 07:12:30'),(1421,'userid_09eb7cc3ef8f1','InterestUID_402b','2026-01-20 07:12:30'),(1422,'userid_09eb7cc3ef8f1','InterestUID_402c','2026-01-20 07:12:30'),(1423,'userid_09eb7cc3ef8f1','InterestUID_403a','2026-01-20 07:12:30'),(1424,'userid_09eb7cc3ef8f1','InterestUID_403b','2026-01-20 07:12:30'),(1425,'userid_09eb7cc3ef8f1','InterestUID_404a','2026-01-20 07:12:30'),(1426,'userid_09eb7cc3ef8f1','InterestUID_404b','2026-01-20 07:12:30'),(1427,'userid_09eb7cc3ef8f1','InterestUID_405a','2026-01-20 07:12:30'),(1428,'userid_09eb7cc3ef8f1','InterestUID_405b','2026-01-20 07:12:30'),(1429,'userid_09eb7cc3ef8f1','InterestUID_405c','2026-01-20 07:12:30'),(1430,'userid_09eb7cc3ef8f1','InterestUID_501a','2026-01-20 07:12:30'),(1431,'userid_09eb7cc3ef8f1','InterestUID_501b','2026-01-20 07:12:30'),(1432,'userid_09eb7cc3ef8f1','InterestUID_502a','2026-01-20 07:12:30'),(1433,'userid_09eb7cc3ef8f1','InterestUID_502b','2026-01-20 07:12:30'),(1434,'userid_09eb7cc3ef8f1','InterestUID_503a','2026-01-20 07:12:30'),(1435,'userid_09eb7cc3ef8f1','InterestUID_503b','2026-01-20 07:12:30'),(1436,'userid_09eb7cc3ef8f1','InterestUID_601a','2026-01-20 07:12:30'),(1437,'userid_09eb7cc3ef8f1','InterestUID_601b','2026-01-20 07:12:30'),(1438,'userid_09eb7cc3ef8f1','InterestUID_602a','2026-01-20 07:12:30'),(1439,'userid_09eb7cc3ef8f1','InterestUID_602b','2026-01-20 07:12:30'),(1440,'userid_09eb7cc3ef8f1','InterestUID_602c','2026-01-20 07:12:30'),(1441,'userid_09eb7cc3ef8f1','InterestUID_603a','2026-01-20 07:12:30'),(1442,'userid_09eb7cc3ef8f1','InterestUID_603b','2026-01-20 07:12:30'),(1443,'userid_09eb7cc3ef8f1','InterestUID_603c','2026-01-20 07:12:30'),(1444,'userid_09eb7cc3ef8f1','InterestUID_701a','2026-01-20 07:12:30'),(1445,'userid_09eb7cc3ef8f1','InterestUID_701b','2026-01-20 07:12:30'),(1446,'userid_09eb7cc3ef8f1','InterestUID_702a','2026-01-20 07:12:30'),(1447,'userid_09eb7cc3ef8f1','InterestUID_702b','2026-01-20 07:12:30'),(1448,'userid_09eb7cc3ef8f1','InterestUID_703a','2026-01-20 07:12:30'),(1449,'userid_09eb7cc3ef8f1','InterestUID_703b','2026-01-20 07:12:30'),(1450,'userid_09eb7cc3ef8f1','InterestUID_703c','2026-01-20 07:12:30'),(1451,'userid_09eb7cc3ef8f1','InterestUID_703d','2026-01-20 07:12:30'),(1452,'userid_09eb7cc3ef8f1','InterestUID_801a','2026-01-20 07:12:30'),(1453,'userid_09eb7cc3ef8f1','InterestUID_801b','2026-01-20 07:12:30'),(1454,'userid_09eb7cc3ef8f1','InterestUID_802a','2026-01-20 07:12:30'),(1455,'userid_09eb7cc3ef8f1','InterestUID_802b','2026-01-20 07:12:30'),(1456,'userid_09eb7cc3ef8f1','InterestUID_803a','2026-01-20 07:12:30'),(1457,'userid_09eb7cc3ef8f1','InterestUID_803b','2026-01-20 07:12:30'),(1458,'userid_09eb7cc3ef8f1','InterestUID_803c','2026-01-20 07:12:30'),(1459,'userid_09eb7cc3ef8f1','InterestUID_901a','2026-01-20 07:12:30'),(1460,'userid_09eb7cc3ef8f1','InterestUID_901b','2026-01-20 07:12:30'),(1461,'userid_09eb7cc3ef8f1','InterestUID_901c','2026-01-20 07:12:30'),(1462,'userid_09eb7cc3ef8f1','InterestUID_902a','2026-01-20 07:12:30'),(1463,'userid_09eb7cc3ef8f1','InterestUID_902b','2026-01-20 07:12:30'),(1464,'userid_09eb7cc3ef8f1','InterestUID_902c','2026-01-20 07:12:30'),(1465,'userid_09eb7cc3ef8f1','InterestUID_102a','2026-01-20 07:12:30'),(1466,'userid_09eb7cc3ef8f1','InterestUID_102b','2026-01-20 07:12:30'),(1467,'userid_09eb7cc3ef8f1','InterestUID_102c','2026-01-20 07:12:30'),(1468,'userid_09eb7cc3ef8f1','InterestUID_102d','2026-01-20 07:12:30'),(1469,'userid_09eb7cc3ef8f1','InterestUID_102e','2026-01-20 07:12:30'),(1470,'userid_09eb7cc3ef8f1','InterestUID_102f','2026-01-20 07:12:30'),(1471,'userid_09eb7cc3ef8f1','InterestUID_102g','2026-01-20 07:12:30'),(1472,'userid_09eb7cc3ef8f1','InterestUID_102h','2026-01-20 07:12:30'),(1556,'userid_d593d38eed2a1','InterestUID_101a','2026-03-17 06:27:37'),(1557,'userid_d593d38eed2a1','InterestUID_101b','2026-03-17 06:27:37'),(1558,'userid_d593d38eed2a1','InterestUID_101c','2026-03-17 06:27:37'),(1559,'userid_d593d38eed2a1','InterestUID_101d','2026-03-17 06:27:37'),(1560,'userid_d593d38eed2a1','InterestUID_101e','2026-03-17 06:27:37'),(1561,'userid_d593d38eed2a1','InterestUID_101f','2026-03-17 06:27:37'),(1562,'userid_d593d38eed2a1','InterestUID_101g','2026-03-17 06:27:37'),(1563,'userid_d593d38eed2a1','InterestUID_103a','2026-03-17 06:27:37'),(1564,'userid_d593d38eed2a1','InterestUID_103b','2026-03-17 06:27:37'),(1565,'userid_d593d38eed2a1','InterestUID_103c','2026-03-17 06:27:37'),(1566,'userid_d593d38eed2a1','InterestUID_1001a','2026-03-17 06:27:37'),(1567,'userid_d593d38eed2a1','InterestUID_1001b','2026-03-17 06:27:37'),(1568,'userid_d593d38eed2a1','InterestUID_1001c','2026-03-17 06:27:37'),(1569,'userid_d593d38eed2a1','InterestUID_301a','2026-03-17 06:27:37'),(1570,'userid_d593d38eed2a1','InterestUID_301b','2026-03-17 06:27:37'),(1571,'userid_d593d38eed2a1','InterestUID_301c','2026-03-17 06:27:37'),(1572,'userid_d593d38eed2a1','InterestUID_302a','2026-03-17 06:27:37'),(1573,'userid_d593d38eed2a1','InterestUID_302b','2026-03-17 06:27:37'),(1574,'userid_d593d38eed2a1','InterestUID_303a','2026-03-17 06:27:37'),(1575,'userid_d593d38eed2a1','InterestUID_303b','2026-03-17 06:27:37'),(1576,'userid_d593d38eed2a1','InterestUID_303c','2026-03-17 06:27:37'),(1577,'userid_d593d38eed2a1','InterestUID_401a','2026-03-17 06:27:37'),(1578,'userid_d593d38eed2a1','InterestUID_401b','2026-03-17 06:27:37'),(1579,'userid_d593d38eed2a1','InterestUID_402a','2026-03-17 06:27:37'),(1580,'userid_d593d38eed2a1','InterestUID_402b','2026-03-17 06:27:37'),(1581,'userid_d593d38eed2a1','InterestUID_402c','2026-03-17 06:27:37'),(1582,'userid_d593d38eed2a1','InterestUID_403a','2026-03-17 06:27:37'),(1583,'userid_d593d38eed2a1','InterestUID_403b','2026-03-17 06:27:37'),(1584,'userid_d593d38eed2a1','InterestUID_404a','2026-03-17 06:27:37'),(1585,'userid_d593d38eed2a1','InterestUID_404b','2026-03-17 06:27:37'),(1586,'userid_d593d38eed2a1','InterestUID_405a','2026-03-17 06:27:37'),(1587,'userid_d593d38eed2a1','InterestUID_405b','2026-03-17 06:27:37'),(1588,'userid_d593d38eed2a1','InterestUID_405c','2026-03-17 06:27:37'),(1589,'userid_d593d38eed2a1','InterestUID_501a','2026-03-17 06:27:37'),(1590,'userid_d593d38eed2a1','InterestUID_501b','2026-03-17 06:27:37'),(1591,'userid_d593d38eed2a1','InterestUID_502a','2026-03-17 06:27:37'),(1592,'userid_d593d38eed2a1','InterestUID_502b','2026-03-17 06:27:37'),(1593,'userid_d593d38eed2a1','InterestUID_503a','2026-03-17 06:27:37'),(1594,'userid_d593d38eed2a1','InterestUID_503b','2026-03-17 06:27:37'),(1595,'userid_d593d38eed2a1','InterestUID_601a','2026-03-17 06:27:37'),(1596,'userid_d593d38eed2a1','InterestUID_601b','2026-03-17 06:27:37'),(1597,'userid_d593d38eed2a1','InterestUID_602a','2026-03-17 06:27:37'),(1598,'userid_d593d38eed2a1','InterestUID_602b','2026-03-17 06:27:37'),(1599,'userid_d593d38eed2a1','InterestUID_602c','2026-03-17 06:27:37'),(1600,'userid_d593d38eed2a1','InterestUID_603a','2026-03-17 06:27:37'),(1601,'userid_d593d38eed2a1','InterestUID_603b','2026-03-17 06:27:37'),(1602,'userid_d593d38eed2a1','InterestUID_603c','2026-03-17 06:27:37'),(1603,'userid_d593d38eed2a1','InterestUID_701a','2026-03-17 06:27:37'),(1604,'userid_d593d38eed2a1','InterestUID_701b','2026-03-17 06:27:37'),(1605,'userid_d593d38eed2a1','InterestUID_702a','2026-03-17 06:27:37'),(1606,'userid_d593d38eed2a1','InterestUID_702b','2026-03-17 06:27:37'),(1607,'userid_d593d38eed2a1','InterestUID_703a','2026-03-17 06:27:37'),(1608,'userid_d593d38eed2a1','InterestUID_703b','2026-03-17 06:27:37'),(1609,'userid_d593d38eed2a1','InterestUID_703c','2026-03-17 06:27:37'),(1610,'userid_d593d38eed2a1','InterestUID_703d','2026-03-17 06:27:37'),(1611,'userid_d593d38eed2a1','InterestUID_801a','2026-03-17 06:27:37'),(1612,'userid_d593d38eed2a1','InterestUID_801b','2026-03-17 06:27:37'),(1613,'userid_d593d38eed2a1','InterestUID_802a','2026-03-17 06:27:37'),(1614,'userid_d593d38eed2a1','InterestUID_802b','2026-03-17 06:27:37'),(1615,'userid_d593d38eed2a1','InterestUID_803a','2026-03-17 06:27:37'),(1616,'userid_d593d38eed2a1','InterestUID_803b','2026-03-17 06:27:37'),(1617,'userid_d593d38eed2a1','InterestUID_803c','2026-03-17 06:27:37'),(1618,'userid_d593d38eed2a1','InterestUID_201a','2026-03-17 06:27:37'),(1619,'userid_d593d38eed2a1','InterestUID_201b','2026-03-17 06:27:37'),(1620,'userid_d593d38eed2a1','InterestUID_202a','2026-03-17 06:27:37'),(1621,'userid_d593d38eed2a1','InterestUID_202b','2026-03-17 06:27:37'),(1622,'userid_d593d38eed2a1','InterestUID_203a','2026-03-17 06:27:37'),(1623,'userid_d593d38eed2a1','InterestUID_203b','2026-03-17 06:27:37'),(1624,'userid_d593d38eed2a1','InterestUID_203c','2026-03-17 06:27:37'),(1625,'userid_d593d38eed2a1','InterestUID_901a','2026-03-17 06:27:37'),(1626,'userid_d593d38eed2a1','InterestUID_901b','2026-03-17 06:27:37'),(1627,'userid_d593d38eed2a1','InterestUID_901c','2026-03-17 06:27:37'),(1628,'userid_d593d38eed2a1','InterestUID_902a','2026-03-17 06:27:37'),(1629,'userid_d593d38eed2a1','InterestUID_902b','2026-03-17 06:27:37'),(1630,'userid_d593d38eed2a1','InterestUID_902c','2026-03-17 06:27:37'),(1631,'userid_d593d38eed2a1','InterestUID_102a','2026-03-17 06:27:37'),(1632,'userid_d593d38eed2a1','InterestUID_102b','2026-03-17 06:27:37'),(1633,'userid_d593d38eed2a1','InterestUID_102c','2026-03-17 06:27:37'),(1634,'userid_d593d38eed2a1','InterestUID_102d','2026-03-17 06:27:37'),(1635,'userid_d593d38eed2a1','InterestUID_102e','2026-03-17 06:27:37'),(1636,'userid_d593d38eed2a1','InterestUID_102f','2026-03-17 06:27:37'),(1637,'userid_d593d38eed2a1','InterestUID_102g','2026-03-17 06:27:37'),(1638,'userid_d593d38eed2a1','InterestUID_102h','2026-03-17 06:27:37'),(1639,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_101a','2026-03-17 08:03:32'),(1640,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_101b','2026-03-17 08:03:32'),(1641,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_101c','2026-03-17 08:03:32'),(1642,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_101d','2026-03-17 08:03:32'),(1643,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_101e','2026-03-17 08:03:32'),(1644,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_103b','2026-03-17 08:03:32'),(1645,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_103c','2026-03-17 08:03:32'),(1646,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_1001c','2026-03-17 08:03:32'),(1647,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_201a','2026-03-17 08:03:32'),(1648,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_201b','2026-03-17 08:03:32'),(1649,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_202a','2026-03-17 08:03:32'),(1650,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_202b','2026-03-17 08:03:32'),(1651,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_203a','2026-03-17 08:03:32'),(1652,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_203b','2026-03-17 08:03:32'),(1653,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_203c','2026-03-17 08:03:32'),(1654,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_301a','2026-03-17 08:03:32'),(1655,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_301b','2026-03-17 08:03:32'),(1656,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_301c','2026-03-17 08:03:32'),(1657,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_302a','2026-03-17 08:03:32'),(1658,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_302b','2026-03-17 08:03:32'),(1659,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_303b','2026-03-17 08:03:32'),(1660,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_303c','2026-03-17 08:03:32'),(1661,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_401a','2026-03-17 08:03:32'),(1662,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_401b','2026-03-17 08:03:32'),(1663,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_402b','2026-03-17 08:03:32'),(1664,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_402c','2026-03-17 08:03:32'),(1665,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_403b','2026-03-17 08:03:32'),(1666,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_404a','2026-03-17 08:03:32'),(1667,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_404b','2026-03-17 08:03:32'),(1668,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_405a','2026-03-17 08:03:32'),(1669,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_405b','2026-03-17 08:03:32'),(1670,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_405c','2026-03-17 08:03:32'),(1671,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_501b','2026-03-17 08:03:32'),(1672,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_502a','2026-03-17 08:03:32'),(1673,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_502b','2026-03-17 08:03:32'),(1674,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_503a','2026-03-17 08:03:32'),(1675,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_503b','2026-03-17 08:03:32'),(1676,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_601a','2026-03-17 08:03:32'),(1677,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_601b','2026-03-17 08:03:32'),(1678,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_602a','2026-03-17 08:03:32'),(1679,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_602b','2026-03-17 08:03:32'),(1680,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_602c','2026-03-17 08:03:32'),(1681,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_603a','2026-03-17 08:03:32'),(1682,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_603b','2026-03-17 08:03:32'),(1683,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_603c','2026-03-17 08:03:32'),(1684,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_701a','2026-03-17 08:03:32'),(1685,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_701b','2026-03-17 08:03:32'),(1686,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_702a','2026-03-17 08:03:32'),(1687,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_702b','2026-03-17 08:03:32'),(1688,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_703a','2026-03-17 08:03:32'),(1689,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_703b','2026-03-17 08:03:32'),(1690,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_703c','2026-03-17 08:03:32'),(1691,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_703d','2026-03-17 08:03:32'),(1692,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_102a','2026-03-17 08:03:32'),(1693,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_102b','2026-03-17 08:03:32'),(1694,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_102c','2026-03-17 08:03:32'),(1695,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_102d','2026-03-17 08:03:32'),(1696,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_102e','2026-03-17 08:03:32'),(1697,'userid_368a282f21d711f1b69fea35c04f5bf0','InterestUID_102f','2026-03-17 08:03:32'),(1698,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_101a','2026-03-18 01:19:36'),(1699,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_101b','2026-03-18 01:19:36'),(1700,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_101c','2026-03-18 01:19:36'),(1701,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_101d','2026-03-18 01:19:36'),(1702,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_101e','2026-03-18 01:19:36'),(1703,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_101f','2026-03-18 01:19:36'),(1704,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_101g','2026-03-18 01:19:36'),(1705,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_103b','2026-03-18 01:19:36'),(1706,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_103c','2026-03-18 01:19:36'),(1707,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_1001a','2026-03-18 01:19:36'),(1708,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_1001b','2026-03-18 01:19:36'),(1709,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_1001c','2026-03-18 01:19:36'),(1710,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_201a','2026-03-18 01:19:36'),(1711,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_201b','2026-03-18 01:19:36'),(1712,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_202b','2026-03-18 01:19:36'),(1713,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_203a','2026-03-18 01:19:36'),(1714,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_203b','2026-03-18 01:19:36'),(1715,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_301a','2026-03-18 01:19:36'),(1716,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_301b','2026-03-18 01:19:36'),(1717,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_301c','2026-03-18 01:19:36'),(1718,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_302b','2026-03-18 01:19:36'),(1719,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_303a','2026-03-18 01:19:36'),(1720,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_303b','2026-03-18 01:19:36'),(1721,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_303c','2026-03-18 01:19:36'),(1722,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_401a','2026-03-18 01:19:36'),(1723,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_401b','2026-03-18 01:19:36'),(1724,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_402a','2026-03-18 01:19:36'),(1725,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_402b','2026-03-18 01:19:36'),(1726,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_402c','2026-03-18 01:19:36'),(1727,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_403b','2026-03-18 01:19:36'),(1728,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_404a','2026-03-18 01:19:36'),(1729,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_404b','2026-03-18 01:19:36'),(1730,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_405a','2026-03-18 01:19:36'),(1731,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_405b','2026-03-18 01:19:36'),(1732,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_501a','2026-03-18 01:19:36'),(1733,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_501b','2026-03-18 01:19:36'),(1734,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_502a','2026-03-18 01:19:36'),(1735,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_502b','2026-03-18 01:19:36'),(1736,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_503a','2026-03-18 01:19:36'),(1737,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_503b','2026-03-18 01:19:36'),(1738,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_601a','2026-03-18 01:19:36'),(1739,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_601b','2026-03-18 01:19:36'),(1740,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_602a','2026-03-18 01:19:36'),(1741,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_602b','2026-03-18 01:19:36'),(1742,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_602c','2026-03-18 01:19:36'),(1743,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_603a','2026-03-18 01:19:36'),(1744,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_603b','2026-03-18 01:19:36'),(1745,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_603c','2026-03-18 01:19:36'),(1746,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_701a','2026-03-18 01:19:36'),(1747,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_701b','2026-03-18 01:19:36'),(1748,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_702a','2026-03-18 01:19:36'),(1749,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_702b','2026-03-18 01:19:36'),(1750,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_703a','2026-03-18 01:19:36'),(1751,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_703b','2026-03-18 01:19:36'),(1752,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_703c','2026-03-18 01:19:36'),(1753,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_703d','2026-03-18 01:19:36'),(1754,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_801a','2026-03-18 01:19:36'),(1755,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_801b','2026-03-18 01:19:36'),(1756,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_802a','2026-03-18 01:19:36'),(1757,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_802b','2026-03-18 01:19:36'),(1758,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_803a','2026-03-18 01:19:36'),(1759,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_803b','2026-03-18 01:19:36'),(1760,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_803c','2026-03-18 01:19:36'),(1761,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_901a','2026-03-18 01:19:36'),(1762,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_901b','2026-03-18 01:19:36'),(1763,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_901c','2026-03-18 01:19:36'),(1764,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_902a','2026-03-18 01:19:36'),(1765,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_902b','2026-03-18 01:19:36'),(1766,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_902c','2026-03-18 01:19:36'),(1767,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_102a','2026-03-18 01:19:36'),(1768,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_102b','2026-03-18 01:19:36'),(1769,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_102c','2026-03-18 01:19:36'),(1770,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_102d','2026-03-18 01:19:36'),(1771,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_102e','2026-03-18 01:19:36'),(1772,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_102f','2026-03-18 01:19:36'),(1773,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_102g','2026-03-18 01:19:36'),(1774,'userid_eefc261620ff11f1b69fea35c04f5bf0','InterestUID_102h','2026-03-18 01:19:36'),(1775,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_101a','2026-03-27 06:40:17'),(1776,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_101b','2026-03-27 06:40:17'),(1777,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_101c','2026-03-27 06:40:17'),(1778,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_101d','2026-03-27 06:40:17'),(1779,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_101e','2026-03-27 06:40:17'),(1780,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_101f','2026-03-27 06:40:17'),(1781,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_101g','2026-03-27 06:40:17'),(1782,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_103a','2026-03-27 06:40:17'),(1783,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_103b','2026-03-27 06:40:17'),(1784,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_103c','2026-03-27 06:40:17'),(1785,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_1001a','2026-03-27 06:40:17'),(1786,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_1001b','2026-03-27 06:40:17'),(1787,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_1001c','2026-03-27 06:40:17'),(1788,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_401a','2026-03-27 06:40:17'),(1789,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_401b','2026-03-27 06:40:17'),(1790,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_402a','2026-03-27 06:40:17'),(1791,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_402b','2026-03-27 06:40:17'),(1792,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_402c','2026-03-27 06:40:17'),(1793,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_403a','2026-03-27 06:40:17'),(1794,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_403b','2026-03-27 06:40:17'),(1795,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_404a','2026-03-27 06:40:17'),(1796,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_404b','2026-03-27 06:40:17'),(1797,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_405a','2026-03-27 06:40:17'),(1798,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_405b','2026-03-27 06:40:17'),(1799,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_405c','2026-03-27 06:40:17'),(1800,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_501a','2026-03-27 06:40:17'),(1801,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_501b','2026-03-27 06:40:17'),(1802,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_502a','2026-03-27 06:40:17'),(1803,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_502b','2026-03-27 06:40:17'),(1804,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_503a','2026-03-27 06:40:17'),(1805,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_503b','2026-03-27 06:40:17'),(1806,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_601a','2026-03-27 06:40:17'),(1807,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_601b','2026-03-27 06:40:17'),(1808,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_602a','2026-03-27 06:40:17'),(1809,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_602b','2026-03-27 06:40:17'),(1810,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_602c','2026-03-27 06:40:17'),(1811,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_603a','2026-03-27 06:40:17'),(1812,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_603b','2026-03-27 06:40:17'),(1813,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_603c','2026-03-27 06:40:17'),(1814,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_701a','2026-03-27 06:40:17'),(1815,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_701b','2026-03-27 06:40:17'),(1816,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_702a','2026-03-27 06:40:17'),(1817,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_702b','2026-03-27 06:40:17'),(1818,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_703a','2026-03-27 06:40:17'),(1819,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_703b','2026-03-27 06:40:17'),(1820,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_703c','2026-03-27 06:40:17'),(1821,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_703d','2026-03-27 06:40:17'),(1822,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_801a','2026-03-27 06:40:17'),(1823,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_801b','2026-03-27 06:40:17'),(1824,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_802a','2026-03-27 06:40:17'),(1825,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_802b','2026-03-27 06:40:17'),(1826,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_803a','2026-03-27 06:40:17'),(1827,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_803b','2026-03-27 06:40:17'),(1828,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_803c','2026-03-27 06:40:17'),(1829,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_901a','2026-03-27 06:40:17'),(1830,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_901b','2026-03-27 06:40:17'),(1831,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_901c','2026-03-27 06:40:17'),(1832,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_902a','2026-03-27 06:40:17'),(1833,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_902b','2026-03-27 06:40:17'),(1834,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_902c','2026-03-27 06:40:17'),(1835,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_201a','2026-03-27 06:40:17'),(1836,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_201b','2026-03-27 06:40:17'),(1837,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_202a','2026-03-27 06:40:17'),(1838,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_202b','2026-03-27 06:40:17'),(1839,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_203a','2026-03-27 06:40:17'),(1840,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_203b','2026-03-27 06:40:17'),(1841,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_203c','2026-03-27 06:40:17'),(1842,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_301a','2026-03-27 06:40:17'),(1843,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_301b','2026-03-27 06:40:17'),(1844,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_301c','2026-03-27 06:40:17'),(1845,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_302a','2026-03-27 06:40:17'),(1846,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_302b','2026-03-27 06:40:17'),(1847,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_303a','2026-03-27 06:40:17'),(1848,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_303b','2026-03-27 06:40:17'),(1849,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_303c','2026-03-27 06:40:17'),(1850,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_102a','2026-03-27 06:40:17'),(1851,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_102b','2026-03-27 06:40:17'),(1852,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_102c','2026-03-27 06:40:17'),(1853,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_102d','2026-03-27 06:40:17'),(1854,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_102e','2026-03-27 06:40:17'),(1855,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_102f','2026-03-27 06:40:17'),(1856,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_102g','2026-03-27 06:40:17'),(1857,'userid_8a6a4e1d29a711f198b73a33889a1b82','InterestUID_102h','2026-03-27 06:40:17');
/*!40000 ALTER TABLE `user_interest_map` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `user_interests`
--

DROP TABLE IF EXISTS `user_interests`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_interests` (
  `InterestUID` varchar(20) NOT NULL,
  `CategoryID` int NOT NULL,
  `CategoryName` varchar(100) NOT NULL,
  `LevelCode` char(1) NOT NULL,
  `LevelName` varchar(100) NOT NULL,
  `InterestCode` varchar(10) NOT NULL,
  `InterestDescription` varchar(255) DEFAULT NULL,
  `CreatedAt` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `UpdatedAt` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`InterestUID`),
  UNIQUE KEY `uq_interest_code` (`InterestCode`),
  KEY `idx_interest_category` (`CategoryID`),
  KEY `idx_interest_category_level` (`CategoryID`,`LevelCode`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user_interests`
--

LOCK TABLES `user_interests` WRITE;
/*!40000 ALTER TABLE `user_interests` DISABLE KEYS */;
INSERT INTO `user_interests` VALUES ('InterestUID_1001a',1001,'Mobility / Education – Context','a','Student','ME1001a','Interested in products or trials related to student use','2026-01-03 09:56:05','2026-01-03 09:56:05'),('InterestUID_1001b',1001,'Mobility / Education – Context','b','Educator','ME1001b','Interested in products or trials related to teaching or education','2026-01-03 09:56:05','2026-01-03 09:56:05'),('InterestUID_1001c',1001,'Mobility / Education – Context','c','Mobile / On-the-Go Use','ME1001c','Interested in products designed for mobile or on-the-go use','2026-01-03 09:56:05','2026-01-03 09:56:05'),('InterestUID_101a',101,'Brand','a','Logitech / Logi','BR101a','Interest in Logitech / Logi branded products','2026-01-03 09:30:00','2026-01-03 09:30:00'),('InterestUID_101b',101,'Brand','b','Logitech G','BR101b','Interest in Logitech G gaming products','2026-01-03 09:30:00','2026-01-03 09:30:00'),('InterestUID_101c',101,'Brand','c','ASTRO Gaming','BR101c','Interest in ASTRO Gaming products','2026-01-03 09:30:00','2026-01-03 09:30:00'),('InterestUID_101d',101,'Brand','d','Ultimate Ears (UE)','BR101d','Interest in Ultimate Ears audio products','2026-01-03 09:30:00','2026-01-03 09:30:00'),('InterestUID_101e',101,'Brand','e','Jaybird','BR101e','Interest in Jaybird wireless audio products','2026-01-03 09:30:00','2026-01-03 09:30:00'),('InterestUID_101f',101,'Brand','f','Blue Microphones','BR101f','Interest in Blue Microphones audio products','2026-01-03 09:30:00','2026-01-03 09:30:00'),('InterestUID_101g',101,'Brand','g','Streamlabs','BR101g','Interest in Streamlabs streaming tools','2026-01-03 09:30:00','2026-01-03 09:30:00'),('InterestUID_102a',102,'Product Type','a','Keyboards','PT102a','Interest in keyboards of any type','2026-01-03 09:32:07','2026-01-03 09:32:07'),('InterestUID_102b',102,'Product Type','b','Mice','PT102b','Interest in mice and pointing devices','2026-01-03 09:32:07','2026-01-03 09:32:07'),('InterestUID_102c',102,'Product Type','c','Headsets','PT102c','Interest in over-ear or on-ear headsets','2026-01-03 09:32:07','2026-01-03 09:32:07'),('InterestUID_102d',102,'Product Type','d','Earbuds','PT102d','Interest in wired or wireless earbuds','2026-01-03 09:32:07','2026-01-03 09:32:07'),('InterestUID_102e',102,'Product Type','e','Speakers','PT102e','Interest in desktop or portable speakers','2026-01-03 09:32:07','2026-01-03 09:32:07'),('InterestUID_102f',102,'Product Type','f','Microphones','PT102f','Interest in standalone microphones','2026-01-03 09:32:07','2026-01-03 09:32:07'),('InterestUID_102g',102,'Product Type','g','Webcams','PT102g','Interest in webcams and video capture devices','2026-01-03 09:32:07','2026-01-03 09:32:07'),('InterestUID_102h',102,'Product Type','h','Streaming / Creator Gear','PT102h','Interest in streaming, creator, and broadcast-related gear','2026-01-03 09:32:07','2026-01-03 09:32:07'),('InterestUID_103a',103,'Product Tier','a','Entry Level','TR103a','Generally interested in entry-level or budget-friendly products','2026-01-03 09:33:24','2026-01-03 09:33:24'),('InterestUID_103b',103,'Product Tier','b','Mid Tier','TR103b','Generally interested in mid-range products balancing features and value','2026-01-03 09:33:24','2026-01-03 09:33:24'),('InterestUID_103c',103,'Product Tier','c','High End','TR103c','Generally interested in premium or high-end products','2026-01-03 09:33:24','2026-01-03 09:33:24'),('InterestUID_201a',201,'Keyboard – Key Type','a','Mechanical','KB201a','Interested in mechanical keyboards','2026-01-03 09:37:50','2026-01-03 09:37:50'),('InterestUID_201b',201,'Keyboard – Key Type','b','Non-Mechanical','KB201b','Interested in non-mechanical keyboards (membrane, scissor, etc.)','2026-01-03 09:37:50','2026-01-03 09:37:50'),('InterestUID_202a',202,'Keyboard – Connection','a','Wired','KB202a','Interested in wired keyboards','2026-01-03 09:37:55','2026-01-03 09:37:55'),('InterestUID_202b',202,'Keyboard – Connection','b','Wireless','KB202b','Interested in wireless keyboards','2026-01-03 09:37:55','2026-01-03 09:37:55'),('InterestUID_203a',203,'Keyboard – Form Factor','a','Full Size','KB203a','Interested in full-size keyboards','2026-01-03 09:38:04','2026-01-03 09:38:04'),('InterestUID_203b',203,'Keyboard – Form Factor','b','Compact / Tenkeyless','KB203b','Interested in compact or tenkeyless keyboards','2026-01-03 09:38:04','2026-01-03 09:38:04'),('InterestUID_203c',203,'Keyboard – Form Factor','c','Low Profile','KB203c','Interested in low-profile keyboards','2026-01-03 09:38:04','2026-01-03 09:38:04'),('InterestUID_301a',301,'Mouse – Grip Type','a','Palm Grip','MS301a','Interested in palm-grip style mice','2026-01-03 09:40:25','2026-01-03 09:40:25'),('InterestUID_301b',301,'Mouse – Grip Type','b','Claw Grip','MS301b','Interested in claw-grip style mice','2026-01-03 09:40:25','2026-01-03 09:40:25'),('InterestUID_301c',301,'Mouse – Grip Type','c','Fingertip Grip','MS301c','Interested in fingertip-grip style mice','2026-01-03 09:40:25','2026-01-03 09:40:25'),('InterestUID_302a',302,'Mouse – Connection','a','Wired','MS302a','Interested in wired mice','2026-01-03 09:40:29','2026-01-03 09:40:29'),('InterestUID_302b',302,'Mouse – Connection','b','Wireless','MS302b','Interested in wireless mice','2026-01-03 09:40:29','2026-01-03 09:40:29'),('InterestUID_303a',303,'Mouse – Style','a','Lifestyle','MS303a','Interested in lifestyle-focused mice (compact, minimal, portable)','2026-01-03 09:40:35','2026-01-03 09:40:35'),('InterestUID_303b',303,'Mouse – Style','b','Productivity','MS303b','Interested in productivity-focused mice (comfort, features, everyday use)','2026-01-03 09:40:35','2026-01-03 09:40:35'),('InterestUID_303c',303,'Mouse – Style','c','Gaming','MS303c','Interested in gaming-focused mice (performance, precision, esports)','2026-01-03 09:40:35','2026-01-03 09:40:35'),('InterestUID_401a',401,'Headset – Fit','a','Over-Ear','HS401a','Interested in over-ear headsets','2026-01-03 09:42:57','2026-01-03 09:42:57'),('InterestUID_401b',401,'Headset – Fit','b','On-Ear','HS401b','Interested in on-ear headsets','2026-01-03 09:42:57','2026-01-03 09:42:57'),('InterestUID_402a',402,'Headset – Use Case','a','Work / Productivity','HS402a','Interested in headsets for work, meetings, or productivity','2026-01-03 09:43:25','2026-01-03 09:43:25'),('InterestUID_402b',402,'Headset – Use Case','b','Gaming','HS402b','Interested in headsets for gaming','2026-01-03 09:43:25','2026-01-03 09:43:25'),('InterestUID_402c',402,'Headset – Use Case','c','Both Work and Gaming','HS402c','Interested in headsets suitable for both work and gaming','2026-01-03 09:43:25','2026-01-03 09:43:25'),('InterestUID_403a',403,'Headset – Connection','a','Wired','HS403a','Interested in wired headsets','2026-01-03 09:43:31','2026-01-03 09:43:31'),('InterestUID_403b',403,'Headset – Connection','b','Wireless','HS403b','Interested in wireless headsets','2026-01-03 09:43:31','2026-01-03 09:43:31'),('InterestUID_404a',404,'Headset – Isolation','a','Noise Cancelling','HS404a','Interested in noise-cancelling headsets','2026-01-03 09:43:39','2026-01-03 09:43:39'),('InterestUID_404b',404,'Headset – Isolation','b','Open / Ambient','HS404b','Interested in open or ambient sound headsets','2026-01-03 09:43:39','2026-01-03 09:43:39'),('InterestUID_405a',405,'Headset – Microphone','a','Boom Microphone','HS405a','Interested in headsets with a boom microphone','2026-01-03 09:43:48','2026-01-03 09:43:48'),('InterestUID_405b',405,'Headset – Microphone','b','Integrated / Inline Mic','HS405b','Interested in headsets with an integrated or inline microphone','2026-01-03 09:43:48','2026-01-03 09:43:48'),('InterestUID_405c',405,'Headset – Microphone','c','No Microphone Needed','HS405c','Interested in headsets primarily for listening','2026-01-03 09:43:48','2026-01-03 09:43:48'),('InterestUID_501a',501,'Earbuds – Connection','a','Wired','EB501a','Interested in wired earbuds','2026-01-03 09:45:48','2026-01-03 09:45:48'),('InterestUID_501b',501,'Earbuds – Connection','b','Wireless','EB501b','Interested in wireless earbuds','2026-01-03 09:45:48','2026-01-03 09:45:48'),('InterestUID_502a',502,'Earbuds – Fit Type','a','In-Ear','EB502a','Interested in in-ear earbuds with ear tips','2026-01-03 09:45:54','2026-01-03 09:45:54'),('InterestUID_502b',502,'Earbuds – Fit Type','b','Open-Ear','EB502b','Interested in open-ear earbuds that do not seal the ear canal','2026-01-03 09:45:54','2026-01-03 09:45:54'),('InterestUID_503a',503,'Earbuds – Noise Control','a','Active Noise Cancelling','EB503a','Interested in earbuds with active noise cancelling','2026-01-03 09:46:01','2026-01-03 09:46:01'),('InterestUID_503b',503,'Earbuds – Noise Control','b','No Noise Cancelling','EB503b','Interested in earbuds without active noise cancelling','2026-01-03 09:46:01','2026-01-03 09:46:01'),('InterestUID_601a',601,'Speakers – Connection','a','Wired','SP601a','Interested in wired speakers','2026-01-03 09:47:39','2026-01-03 09:47:39'),('InterestUID_601b',601,'Speakers – Connection','b','Wireless','SP601b','Interested in wireless speakers','2026-01-03 09:47:39','2026-01-03 09:47:39'),('InterestUID_602a',602,'Speakers – Use Case','a','Work','SP602a','Interested in speakers primarily for work or desk use','2026-01-03 09:47:43','2026-01-03 09:47:43'),('InterestUID_602b',602,'Speakers – Use Case','b','Personal','SP602b','Interested in speakers primarily for personal or leisure use','2026-01-03 09:47:43','2026-01-03 09:47:43'),('InterestUID_602c',602,'Speakers – Use Case','c','Both Work and Personal','SP602c','Interested in speakers suitable for both work and personal use','2026-01-03 09:47:43','2026-01-03 09:47:43'),('InterestUID_603a',603,'Speakers – Size','a','Small','SP603a','Interested in small or compact speakers','2026-01-03 09:47:49','2026-01-03 09:47:49'),('InterestUID_603b',603,'Speakers – Size','b','Medium','SP603b','Interested in medium-sized speakers','2026-01-03 09:47:49','2026-01-03 09:47:49'),('InterestUID_603c',603,'Speakers – Size','c','Large','SP603c','Interested in large or room-filling speakers','2026-01-03 09:47:49','2026-01-03 09:47:49'),('InterestUID_701a',701,'Microphone – Connection','a','Wired','MC701a','Interested in wired microphones','2026-01-03 09:50:09','2026-01-03 09:50:09'),('InterestUID_701b',701,'Microphone – Connection','b','Wireless','MC701b','Interested in wireless microphones','2026-01-03 09:50:09','2026-01-03 09:50:09'),('InterestUID_702a',702,'Microphone – Lighting','a','RGB Lighting','MC702a','Interested in microphones with RGB or visual lighting','2026-01-03 09:50:15','2026-01-03 09:50:15'),('InterestUID_702b',702,'Microphone – Lighting','b','No Lighting','MC702b','Interested in microphones without RGB or visual lighting','2026-01-03 09:50:15','2026-01-03 09:50:15'),('InterestUID_703a',703,'Microphone – Use Context','a','Work / Meetings','MC703a','Interested in microphones for work, meetings, or calls','2026-01-03 09:50:21','2026-01-03 09:50:21'),('InterestUID_703b',703,'Microphone – Use Context','b','Streaming / Content Creation','MC703b','Interested in microphones for streaming or content creation','2026-01-03 09:50:21','2026-01-03 09:50:21'),('InterestUID_703c',703,'Microphone – Use Context','c','Gaming','MC703c','Interested in microphones for gaming or voice chat','2026-01-03 09:50:21','2026-01-03 09:50:21'),('InterestUID_703d',703,'Microphone – Use Context','d','General Use','MC703d','Interested in microphones for general-purpose use','2026-01-03 09:50:21','2026-01-03 09:50:21'),('InterestUID_801a',801,'Webcam – Secure Face Recognition','a','Secure Face Login','WC801a','Interested in webcams that support secure face recognition for device login','2026-01-03 09:52:54','2026-01-03 09:52:54'),('InterestUID_801b',801,'Webcam – Secure Face Recognition','b','No Face Login Needed','WC801b','Not interested in face-recognition-based device login','2026-01-03 09:52:54','2026-01-03 09:52:54'),('InterestUID_802a',802,'Webcam – Privacy','a','Physical Lens Cover','WC802a','Interested in webcams with a physical privacy shutter','2026-01-03 09:52:59','2026-01-03 09:52:59'),('InterestUID_802b',802,'Webcam – Privacy','b','No Lens Cover Needed','WC802b','Does not require a physical privacy shutter','2026-01-03 09:52:59','2026-01-03 09:52:59'),('InterestUID_803a',803,'Webcam – Resolution','a','HD (720p)','WC803a','Interested in HD (720p) webcam resolution','2026-01-03 09:53:03','2026-01-03 09:53:03'),('InterestUID_803b',803,'Webcam – Resolution','b','Full HD (1080p)','WC803b','Interested in Full HD (1080p) webcam resolution','2026-01-03 09:53:03','2026-01-03 09:53:03'),('InterestUID_803c',803,'Webcam – Resolution','c','Ultra HD (4K)','WC803c','Interested in Ultra HD (4K) webcam resolution','2026-01-03 09:53:03','2026-01-03 09:53:03'),('InterestUID_901a',901,'Creator Gear – Type','a','Lighting','CG901a','Interested in creator lighting products','2026-01-03 09:55:46','2026-01-03 09:55:46'),('InterestUID_901b',901,'Creator Gear – Type','b','Cameras (Streaming / PTZ)','CG901b','Interested in streaming or creator-focused cameras','2026-01-03 09:55:46','2026-01-03 09:55:46'),('InterestUID_901c',901,'Creator Gear – Type','c','Creative Control Consoles','CG901c','Interested in creative control consoles for streaming or content creation','2026-01-03 09:55:46','2026-01-03 09:55:46'),('InterestUID_902a',902,'Creator Gear – Use Intent','a','Streaming','CG902a','Interested in creator gear primarily for live streaming','2026-01-03 09:55:50','2026-01-03 09:55:50'),('InterestUID_902b',902,'Creator Gear – Use Intent','b','Content Creation','CG902b','Interested in creator gear for recorded or produced content','2026-01-03 09:55:50','2026-01-03 09:55:50'),('InterestUID_902c',902,'Creator Gear – Use Intent','c','Both Streaming and Creation','CG902c','Interested in creator gear for both live streaming and content creation','2026-01-03 09:55:50','2026-01-03 09:55:50');
/*!40000 ALTER TABLE `user_interests` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `user_legal_acceptance`
--

DROP TABLE IF EXISTS `user_legal_acceptance`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_legal_acceptance` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `user_id` varchar(64) DEFAULT NULL,
  `document_id` bigint unsigned NOT NULL,
  `document_type` varchar(50) NOT NULL,
  `accepted_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_user_document` (`user_id`,`document_type`),
  KEY `idx_document` (`document_id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user_legal_acceptance`
--

LOCK TABLES `user_legal_acceptance` WRITE;
/*!40000 ALTER TABLE `user_legal_acceptance` DISABLE KEYS */;
INSERT INTO `user_legal_acceptance` VALUES (1,'userid_7f3cc1331dec11f1b88b1e1ea10fb097',9,'nda','2026-03-12 08:22:26'),(2,'userid_eefc261620ff11f1b69fea35c04f5bf0',9,'nda','2026-03-16 06:46:53'),(3,'userid_368a282f21d711f1b69fea35c04f5bf0',9,'nda','2026-03-17 07:59:59'),(4,'userid_c60f522b273011f198b73a33889a1b82',9,'nda','2026-03-24 03:24:51'),(5,'userid_8a6a4e1d29a711f198b73a33889a1b82',9,'nda','2026-03-27 06:38:53');
/*!40000 ALTER TABLE `user_legal_acceptance` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `user_office_assignment`
--

DROP TABLE IF EXISTS `user_office_assignment`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_office_assignment` (
  `AssignmentID` int NOT NULL AUTO_INCREMENT,
  `user_id` varchar(64) DEFAULT NULL,
  `OfficeID` varchar(20) NOT NULL,
  `IsPrimary` tinyint(1) NOT NULL DEFAULT '1',
  `CreatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `UpdatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`AssignmentID`),
  KEY `UserID` (`user_id`),
  KEY `OfficeID` (`OfficeID`),
  CONSTRAINT `user_office_assignment_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user_pool` (`user_id`),
  CONSTRAINT `user_office_assignment_ibfk_2` FOREIGN KEY (`OfficeID`) REFERENCES `system_office_locations` (`OfficeID`)
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user_office_assignment`
--

LOCK TABLES `user_office_assignment` WRITE;
/*!40000 ALTER TABLE `user_office_assignment` DISABLE KEYS */;
/*!40000 ALTER TABLE `user_office_assignment` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `user_pool`
--

DROP TABLE IF EXISTS `user_pool`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_pool` (
  `user_id` varchar(64) NOT NULL,
  `Email` varchar(255) NOT NULL,
  `EmailDomain` varchar(100) GENERATED ALWAYS AS (substring_index(`Email`,_utf8mb4'@',-(1))) STORED,
  `PasswordHash` varchar(255) DEFAULT NULL,
  `FirstName` varchar(100) DEFAULT NULL,
  `LastName` varchar(100) DEFAULT NULL,
  `PhoneNumber` varchar(50) DEFAULT NULL,
  `InternalUser` tinyint(1) DEFAULT '0',
  `Status` tinyint(1) DEFAULT '0',
  `Notes` text,
  `GlobalNDA_Status` enum('Not Sent','Sent','Signed','Expired','Revoked') DEFAULT 'Not Sent',
  `GlobalNDA_SentAt` datetime DEFAULT NULL,
  `GlobalNDA_SignedAt` datetime DEFAULT NULL,
  `GuidelinesCompletedAt` datetime DEFAULT NULL,
  `WelcomeSeenAt` datetime DEFAULT NULL,
  `GlobalNDA_Version` varchar(20) DEFAULT NULL,
  `ProfileSignature` varchar(500) DEFAULT NULL,
  `LastLoginAt` datetime DEFAULT NULL,
  `CreatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `UpdatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `gender_hash` char(64) DEFAULT NULL,
  `birth_year_hash` char(64) DEFAULT NULL,
  `country_hash` char(64) DEFAULT NULL,
  `city_hash` char(64) DEFAULT NULL,
  `GlobalNDA_IP_Hash` char(64) DEFAULT NULL,
  `ParticipantStatus` enum('active','withdrawn','cooldown','banned') DEFAULT NULL,
  `ProfileWizardStep` tinyint NOT NULL DEFAULT '0',
  `UnregisteredAt` datetime DEFAULT NULL,
  `UnregisterCooldownUntil` datetime DEFAULT NULL,
  `EmailVerified` tinyint(1) DEFAULT '0',
  `EmailVerificationToken` char(64) DEFAULT NULL,
  `EmailVerificationSentAt` datetime DEFAULT NULL,
  `Gender` varchar(20) DEFAULT NULL,
  `BirthYear` smallint DEFAULT NULL,
  `Country` varchar(100) DEFAULT NULL,
  `City` varchar(100) DEFAULT NULL,
  `profile_completed_at` datetime DEFAULT NULL,
  `profile_updated_at` datetime DEFAULT NULL,
  `InterestsWizardCompleted` tinyint(1) NOT NULL DEFAULT '0',
  `MobileCountryCode` varchar(8) DEFAULT NULL,
  `MobileNational` varchar(32) DEFAULT NULL,
  `MobileE164` varchar(32) DEFAULT NULL,
  `MobileVerifiedAt` datetime DEFAULT NULL,
  `CountryCode` char(2) DEFAULT NULL,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `Email` (`Email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user_pool`
--

LOCK TABLES `user_pool` WRITE;
/*!40000 ALTER TABLE `user_pool` DISABLE KEYS */;
INSERT INTO `user_pool` (`user_id`, `Email`, `PasswordHash`, `FirstName`, `LastName`, `PhoneNumber`, `InternalUser`, `Status`, `Notes`, `GlobalNDA_Status`, `GlobalNDA_SentAt`, `GlobalNDA_SignedAt`, `GuidelinesCompletedAt`, `WelcomeSeenAt`, `GlobalNDA_Version`, `ProfileSignature`, `LastLoginAt`, `CreatedAt`, `UpdatedAt`, `gender_hash`, `birth_year_hash`, `country_hash`, `city_hash`, `GlobalNDA_IP_Hash`, `ParticipantStatus`, `ProfileWizardStep`, `UnregisteredAt`, `UnregisterCooldownUntil`, `EmailVerified`, `EmailVerificationToken`, `EmailVerificationSentAt`, `Gender`, `BirthYear`, `Country`, `City`, `profile_completed_at`, `profile_updated_at`, `InterestsWizardCompleted`, `MobileCountryCode`, `MobileNational`, `MobileE164`, `MobileVerifiedAt`, `CountryCode`) VALUES ('userid_09eb7cc3ef8f1','richardlichunliu@gmail.com','$2b$12$Vm.8Us5MbGgrHzkF6Vs1fO9baod50lIiR5aYXbaRZ0fR6FGCpDSEe','Richard Lichun','Liu',NULL,0,0,NULL,'Signed',NULL,'2026-01-12 08:18:11','2026-01-12 08:18:47','2026-01-12 08:18:59',NULL,NULL,'2026-03-13 03:49:06','2026-01-12 08:16:47','2026-03-13 03:49:06',NULL,NULL,NULL,NULL,NULL,'active',2,NULL,NULL,1,NULL,'2026-01-12 08:16:52','male',1978,'USA','Boston',NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_0b06625a1d1711f1b88b1e1ea10fb097','richardlichunliu@email.com','$2b$12$lR.U2UtUsGdAunoyJq6lU.6KvaFYgOvgzOT8Nb.JisTE3kuFxcT8.','Richard','Liu',NULL,0,0,NULL,'Signed',NULL,'2026-03-11 08:33:35','2026-03-11 08:33:40','2026-03-11 08:39:20',NULL,NULL,NULL,'2026-03-11 06:53:43','2026-03-11 08:39:20',NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,1,NULL,NULL,'male',2007,'UA','Kyev',NULL,NULL,0,'+886','0906112133','+8860906112133',NULL,NULL),('userid_1056b715f03d1','x0richliu@gmail.com','$2b$12$.sHxZaoqziqvyY/bujp5IeRg0d24LAAsS.3Fv8wJ/snzeNDwjjcn.','Rich L.','Liu',NULL,0,0,NULL,'Signed',NULL,'2026-01-13 06:37:35','2026-01-13 06:38:26','2026-01-13 06:38:37',NULL,NULL,'2026-01-13 06:20:49','2026-01-13 05:02:30','2026-01-14 08:00:05',NULL,NULL,NULL,NULL,NULL,'active',3,NULL,NULL,1,NULL,'2026-01-13 05:02:35','non_binary',1990,'USA','Boston',NULL,NULL,0,'+886','0906112133','+8860906112133',NULL,NULL),('userid_25a485371dde11f1b88b1e1ea10fb097','paul@thebeatles.com','$2b$12$QGq7KyymRzo0M6QnsuMHp.HY298E2oWnqqPQ2XIBwapufKX0LsBam','Paul','McCartney',NULL,0,0,NULL,'Signed',NULL,'2026-03-12 06:41:56','2026-03-12 06:41:59','2026-03-12 06:41:59',NULL,NULL,NULL,'2026-03-12 06:38:57','2026-03-12 06:41:59',NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,1,NULL,NULL,'male',1963,'GB','Manchester',NULL,NULL,0,'+44','12345688','+4412345688',NULL,NULL),('userid_2dc610151de011f1b88b1e1ea10fb097','george@thebeatles.com','$2b$12$pZeEwqVrjYE0TCnS2IqDIu2wRey6SlVCxJFPS9Ptb8dk2S9hlCIaG','Richard','Liu',NULL,0,0,NULL,'Signed',NULL,'2026-03-12 06:53:59',NULL,NULL,NULL,NULL,'2026-03-12 06:57:31','2026-03-12 06:53:30','2026-03-12 06:57:31',NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,1,NULL,NULL,'prefer_not_to_say',1901,'GB','Liverpool',NULL,NULL,0,'+886','12345688','+88612345688',NULL,NULL),('userid_4b7dd36d1d0a11f1b88b1e1ea10fb097','jim@email.com','$2b$12$wNht5HiALzUeqmVNoGax1uutfeBeDlILMV2s/ItPJxIwy5X30Uxza','Jim','Lee',NULL,0,0,NULL,'Signed',NULL,'2026-03-11 08:44:54','2026-03-11 08:45:03','2026-03-11 08:45:03',NULL,NULL,'2026-03-11 08:44:01','2026-03-11 05:22:27','2026-03-11 08:45:03',NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,1,NULL,'2026-03-11 05:22:27','male',1968,'KR','Seoul',NULL,NULL,0,'+1','6178913981','+16178913981',NULL,NULL),('userid_4fec82c7eea61','rliu9@logitech.com','$2b$12$qH9QovkWIUYmCinmGisFgu/GGAB8MVpz6ZktQSA106GmjVLYWHeR6','Richard','Liu',NULL,1,0,NULL,'Signed',NULL,'2026-01-11 04:35:55','2026-01-11 04:42:25','2026-01-11 04:42:39',NULL,NULL,'2026-03-31 04:37:41','2026-01-11 04:30:52','2026-03-31 04:38:06',NULL,NULL,NULL,NULL,NULL,'active',3,NULL,NULL,1,NULL,'2026-01-11 04:30:56','male',1978,'Taiwan','Hsinchu',NULL,NULL,1,'+886','0906112133','+8860906112133',NULL,'TW'),('userid_5fa2eee31d0d11f1b88b1e1ea10fb097','richliu@email.com','$2b$12$90eo5KHGPpJSc4gfbCk1fOvOA2HBJxSzFC6K75snQulenCkHMaaKS','Richard','Liu',NULL,0,0,NULL,'Signed',NULL,'2026-03-11 05:46:34','2026-03-11 05:46:37','2026-03-11 05:55:29',NULL,NULL,NULL,'2026-03-11 05:44:30','2026-03-11 05:55:29',NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,1,NULL,NULL,'female',2021,'BJ','Portland',NULL,NULL,0,'+886','0906112133','+8860906112133',NULL,NULL),('userid_730c643a1d0c11f1b88b1e1ea10fb097','richard@email.com','$2b$12$CpQE97EWAW8EsoHeied4m.lh9u.Qzq5MHpwVuiVcT2XCnqEPQaO82','Richard','Liu',NULL,0,0,NULL,'Signed',NULL,'2026-03-11 05:42:22','2026-03-11 05:42:27','2026-03-11 05:43:26',NULL,NULL,'2026-03-11 05:38:17','2026-03-11 05:37:53','2026-03-11 05:43:26',NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,1,NULL,NULL,'male',1978,'TW','New Taipei City',NULL,NULL,0,'+886','0906112133','+8860906112133',NULL,NULL),('userid_7f3cc1331dec11f1b88b1e1ea10fb097','nicha@email.com','$2b$12$h4qSrIGDZFdc3PJj6RPxpOjk9SqV9vxLPLzp.U6X4B23KhKuXH58e','Nichakamon','Ruangdech',NULL,0,0,NULL,'Signed',NULL,'2026-03-12 08:22:25','2026-03-12 08:22:30','2026-03-12 08:22:31',NULL,NULL,NULL,'2026-03-12 08:21:40','2026-03-12 08:22:31',NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,1,NULL,NULL,'female',1989,'TW','Linkou',NULL,NULL,0,'+886','0987074886','+8860987074886',NULL,NULL),('userid_838a4cb91d0b11f1b88b1e1ea10fb097','rich@email.com','$2b$12$Qx5kMXnmoT2Xx00EpzdlCOYUZDuF.6FclfATvJrVE/zWkoBge1RUi',NULL,NULL,NULL,0,0,NULL,'Not Sent',NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-03-11 05:31:11','2026-03-11 05:31:11',NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_8c2a449ff5031','achen12@logitech.com','$2b$12$pAA8jsGk7H9w8Pk0AnVb.O7afUOa/R3Jr26foiPGG.mAYLevt2APy','ariel','chen',NULL,1,0,NULL,'Signed',NULL,'2026-01-19 07:07:24','2026-01-19 07:08:16','2026-01-19 07:08:23',NULL,NULL,'2026-01-19 07:52:55','2026-01-19 06:53:23','2026-01-19 07:52:55',NULL,NULL,NULL,NULL,NULL,'active',3,NULL,NULL,1,NULL,'2026-01-19 06:53:27','non_binary',1900,'Taiwan','Hsinchu City',NULL,NULL,0,'+886','988797010','+886988797010',NULL,NULL),('userid_8f10d38d1d2811f1b88b1e1ea10fb097','harry@email.com','$2b$12$KS5mibYcTYWAer3B9NotQep5RtMm8h2pUDTSlWBz3ybsJGzx0pFs.','Harry','Styles',NULL,0,0,NULL,'Signed',NULL,'2026-03-11 08:59:47','2026-03-11 08:59:50','2026-03-11 08:59:50',NULL,NULL,NULL,'2026-03-11 08:59:06','2026-03-11 08:59:50',NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,1,NULL,NULL,'male',2001,'GB','Manchester',NULL,NULL,0,'+852','1516844684','+8521516844684',NULL,NULL),('userid_90f9324aedc91','x0rliu@gmail.com','$2b$12$wA.JaZp876evNIHllXpoCumjKJsNxme6J51kcNGKjhPH9hqLTmrzq','Richard','Liu',NULL,0,0,NULL,'Signed',NULL,'2026-01-10 02:41:57','2026-01-10 02:42:53','2026-01-10 02:43:14',NULL,NULL,'2026-01-28 02:19:30','2026-01-10 02:10:42','2026-01-28 02:19:30',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,'2026-01-10 02:10:49','male',1978,'Taiwan','New Taipei City',NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_d593d38eed2a1','bhallacy@logitech.com','$2b$12$MZpsCNGJkKE/9fRBlcwV/.L.I0LWilyoMRCj8d8qzgRjwKaYUUDUu','Brian','Hallacy',NULL,1,0,NULL,'Signed',NULL,'2026-01-09 07:16:15','2026-01-09 07:16:50','2026-01-09 07:17:04',NULL,NULL,'2026-03-13 03:44:46','2026-01-09 07:14:27','2026-03-13 03:44:46',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,'2026-01-09 07:14:32','male',1979,'Taiwan','New Taipei City',NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_d65b1a091de011f1b88b1e1ea10fb097','timmy@email.com','$2b$12$fOMk5FPwzAFa6haub1agMOo1UGMjwfgB8S4D3KngyxyDwZ4BUvslm','Tim','Hawkins',NULL,0,0,NULL,'Signed',NULL,'2026-03-12 06:59:20',NULL,NULL,NULL,NULL,'2026-03-12 07:27:32','2026-03-12 06:58:13','2026-03-12 07:27:32',NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,1,NULL,NULL,'non_binary',1989,'TH','Bangkok',NULL,NULL,0,'+1','7818913981','+17818913981',NULL,NULL),('userid_e12c2650f5b71','x0rliu@stlawu.edu','$2b$12$VoBkcJ/3QEkKJ6vJl3BvNO0RBYi7MNOy32/smGjOv3OFMWDuGCGHG','Rich Lichun','Liu',NULL,0,0,NULL,'Signed',NULL,'2026-01-20 04:28:31','2026-01-20 04:33:25','2026-01-20 04:33:31',NULL,NULL,'2026-01-20 04:27:24','2026-01-20 04:24:15','2026-01-20 04:43:29',NULL,NULL,NULL,NULL,NULL,'active',3,NULL,NULL,1,NULL,'2026-01-20 04:24:19','non_binary',1978,'Switzerland','Lausanne',NULL,NULL,0,'+886','0906112133','+8860906112133',NULL,NULL),('userid_eb5a17811ddf11f1b88b1e1ea10fb097','ringo@thebeatles.com','$2b$12$oH6i.3Z8hlwqH00y2dvnVeg78TNIB.IDBA.6cS8rqH8JO95ItK5O2','Ringo','Starr',NULL,0,0,NULL,'Signed',NULL,'2026-03-12 06:52:11','2026-03-12 06:52:14','2026-03-12 06:52:14',NULL,NULL,NULL,'2026-03-12 06:51:38','2026-03-12 06:52:14',NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,1,NULL,NULL,'male',1963,'GB','Liverpool',NULL,NULL,0,'+44','12344565','+4412344565',NULL,NULL),('userid_f8a5983e1d2711f1b88b1e1ea10fb097','x0rliu@email.com','$2b$12$vbheshTatgBggLQZSiRSQeCrIuxC6Kh/WkiljqDl/SnSdxTAy.xxa','Richard','Liu',NULL,0,0,NULL,'Signed',NULL,'2026-03-11 08:55:43','2026-03-11 08:55:46','2026-03-11 08:58:30',NULL,NULL,NULL,'2026-03-11 08:54:53','2026-03-11 08:58:30',NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,1,NULL,NULL,'prefer_not_to_say',2007,'AO','Portland',NULL,NULL,0,'+886','988797010','+886988797010',NULL,NULL),('userid_fb8b4fd007e01','achaurasia1@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Arvind','',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b506807e01','ahess1@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Aleksandra','',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b508e07e01','amartens@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Alyssa','Martens',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b50ac07e01','amasoumi@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Amirhossein','Masoumi',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b50c807e01','asiminoff@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Andrew','Siminoff',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b50e707e01','buhrin@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Branislav','Uhrin',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b510307e01','cbendaoud@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Cyrielle','Bendaoud',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b512107e01','dmahmoud@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Dunnia','Mahmoud',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b513f07e01','eafriyie@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Emmanuel','Afriyie',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b515907e01','gcosta@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Gabriel','Costa',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b517307e01','ikremer@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Iris','Kremer',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b518f07e01','jcostaz@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Justine','Costaz',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b51aa07e01','jtalley@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','John','Talley',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b51c507e01','jtrzesicka@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Julia','Trzesicka',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b51e107e01','kli12@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Daniel KN','Li',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b51fc07e01','ljames@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Liam','James',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b521707e01','mcaelum@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Morgan','Caelum',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b523107e01','mliu9@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Miko','',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b524c07e01','mnicole@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Mary Madeline','Nicole',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b526a07e01','mpedroza@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Mariah','Pedroza',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b528507e01','mrobinson1@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Mika','Robinson',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b52a007e01','mstanley@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Maddie','Stanley',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b52ba07e01','nhealy@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Nathan','Healy',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b52d507e01','njackson1@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Nikiba','Jackson',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b52f107e01','nliu4@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Nero','Liu',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b530d07e01','nramesh@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Nikkitha','Ramesh',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b532707e01','nspear@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Nathan','Spear',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b534207e01','pfitzsimons@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Paul','Fitzsimons',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b535c07e01','pkalyan@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Paulo','Kalyan',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b537607e01','pknef@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Paige','Knef',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b539107e01','ptsai1@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Penny','Tsai',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b53ac07e01','pwaldron@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Philip','Waldron',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b53c807e01','ra2@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Ramkumar','',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b53e207e01','rgopinath@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Rekha','',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b53fd07e01','rgray1@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Russ','Gray',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b541807e01','rheemskerk@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Rick','Heemskerk',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b543507e01','rsingh6@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Rashmi','Singh',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b545107e01','rwood@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Rachel','Wood',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b546d07e01','sbetanzo@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Shirley','Betanzo',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b548907e01','sstevenson@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Samantha','Stevenson',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b54a807e01','swaldron1@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Simon','Waldron',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b54c407e01','tbaraz@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Tony','Baraz',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b54df07e01','tgoodwin@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Tim','Goodwin',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_fb8b54fb07e01','wchang7@logitech.com','$2b$12$0123456789abcdef0123456789abcdef0123456789abcdef012345','Wesley','Chang',NULL,1,0,NULL,'Signed',NULL,'2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'2026-02-12 07:03:49','2026-02-12 07:03:49',NULL,NULL,NULL,NULL,NULL,'active',0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL),('userid_ff73c0d921c911f1861f0217bfe79e01','rliu9@email.com','$2b$12$GiBGcaX4.E0TTyHzSyv7WOaUD.HP7oVrty3AMrVMvS2a9W/tTqTvC',NULL,NULL,NULL,0,0,NULL,'Not Sent',NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-03-17 06:24:48','2026-03-17 06:24:48',NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,NULL);
/*!40000 ALTER TABLE `user_pool` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `user_pool_country_codes`
--

DROP TABLE IF EXISTS `user_pool_country_codes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_pool_country_codes` (
  `CountryCode` char(2) NOT NULL,
  `CountryName` varchar(100) NOT NULL,
  `Region` varchar(50) NOT NULL,
  PRIMARY KEY (`CountryCode`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user_pool_country_codes`
--

LOCK TABLES `user_pool_country_codes` WRITE;
/*!40000 ALTER TABLE `user_pool_country_codes` DISABLE KEYS */;
INSERT INTO `user_pool_country_codes` VALUES ('AD','Andorra','Europe'),('AE','United Arab Emirates','Asia'),('AF','Afghanistan','Asia'),('AG','Antigua and Barbuda','North America'),('AL','Albania','Europe'),('AM','Armenia','Asia'),('AO','Angola','Africa'),('AR','Argentina','South America'),('AT','Austria','Europe'),('AU','Australia','Oceania'),('AZ','Azerbaijan','Asia'),('BA','Bosnia and Herzegovina','Europe'),('BB','Barbados','North America'),('BD','Bangladesh','Asia'),('BE','Belgium','Europe'),('BF','Burkina Faso','Africa'),('BG','Bulgaria','Europe'),('BH','Bahrain','Asia'),('BI','Burundi','Africa'),('BJ','Benin','Africa'),('BN','Brunei','Asia'),('BO','Bolivia','South America'),('BR','Brazil','South America'),('BS','Bahamas','North America'),('BT','Bhutan','Asia'),('BW','Botswana','Africa'),('BY','Belarus','Europe'),('BZ','Belize','North America'),('CA','Canada','North America'),('CD','Democratic Republic of the Congo','Africa'),('CF','Central African Republic','Africa'),('CG','Republic of the Congo','Africa'),('CH','Switzerland','Europe'),('CI','Côte d\'Ivoire','Africa'),('CK','Cook Islands','Oceania'),('CL','Chile','South America'),('CM','Cameroon','Africa'),('CN','China','Asia'),('CO','Colombia','South America'),('CR','Costa Rica','North America'),('CU','Cuba','North America'),('CV','Cape Verde','Africa'),('CY','Cyprus','Asia'),('CZ','Czechia','Europe'),('DE','Germany','Europe'),('DJ','Djibouti','Africa'),('DK','Denmark','Europe'),('DM','Dominica','North America'),('DO','Dominican Republic','North America'),('DZ','Algeria','Africa'),('EC','Ecuador','South America'),('EE','Estonia','Europe'),('EG','Egypt','Africa'),('ER','Eritrea','Africa'),('ES','Spain','Europe'),('ET','Ethiopia','Africa'),('FI','Finland','Europe'),('FJ','Fiji','Oceania'),('FM','Micronesia','Oceania'),('FR','France','Europe'),('GA','Gabon','Africa'),('GB','United Kingdom','Europe'),('GD','Grenada','North America'),('GE','Georgia','Asia'),('GH','Ghana','Africa'),('GI','Gibraltar','Europe'),('GM','Gambia','Africa'),('GN','Guinea','Africa'),('GQ','Equatorial Guinea','Africa'),('GR','Greece','Europe'),('GT','Guatemala','North America'),('GW','Guinea-Bissau','Africa'),('GY','Guyana','South America'),('HN','Honduras','North America'),('HR','Croatia','Europe'),('HT','Haiti','North America'),('HU','Hungary','Europe'),('ID','Indonesia','Asia'),('IE','Ireland','Europe'),('IL','Israel','Asia'),('IM','Isle of Man','Europe'),('IN','India','Asia'),('IQ','Iraq','Asia'),('IR','Iran','Asia'),('IS','Iceland','Europe'),('IT','Italy','Europe'),('JE','Jersey','Europe'),('JM','Jamaica','North America'),('JO','Jordan','Asia'),('JP','Japan','Asia'),('KE','Kenya','Africa'),('KG','Kyrgyzstan','Asia'),('KH','Cambodia','Asia'),('KI','Kiribati','Oceania'),('KM','Comoros','Africa'),('KN','Saint Kitts and Nevis','North America'),('KP','North Korea','Asia'),('KR','South Korea','Asia'),('KW','Kuwait','Asia'),('KZ','Kazakhstan','Asia'),('LA','Laos','Asia'),('LB','Lebanon','Asia'),('LC','Saint Lucia','North America'),('LI','Liechtenstein','Europe'),('LK','Sri Lanka','Asia'),('LR','Liberia','Africa'),('LS','Lesotho','Africa'),('LT','Lithuania','Europe'),('LU','Luxembourg','Europe'),('LV','Latvia','Europe'),('LY','Libya','Africa'),('MA','Morocco','Africa'),('MC','Monaco','Europe'),('MD','Moldova','Europe'),('ME','Montenegro','Europe'),('MG','Madagascar','Africa'),('MH','Marshall Islands','Oceania'),('MK','North Macedonia','Europe'),('ML','Mali','Africa'),('MM','Myanmar','Asia'),('MN','Mongolia','Asia'),('MR','Mauritania','Africa'),('MT','Malta','Europe'),('MU','Mauritius','Africa'),('MV','Maldives','Asia'),('MW','Malawi','Africa'),('MX','Mexico','North America'),('MY','Malaysia','Asia'),('MZ','Mozambique','Africa'),('NA','Namibia','Africa'),('NC','New Caledonia','Oceania'),('NE','Niger','Africa'),('NG','Nigeria','Africa'),('NI','Nicaragua','North America'),('NL','Netherlands','Europe'),('NO','Norway','Europe'),('NP','Nepal','Asia'),('NR','Nauru','Oceania'),('NU','Niue','Oceania'),('NZ','New Zealand','Oceania'),('OM','Oman','Asia'),('PA','Panama','North America'),('PE','Peru','South America'),('PF','French Polynesia','Oceania'),('PG','Papua New Guinea','Oceania'),('PH','Philippines','Asia'),('PK','Pakistan','Asia'),('PL','Poland','Europe'),('PT','Portugal','Europe'),('PW','Palau','Oceania'),('PY','Paraguay','South America'),('QA','Qatar','Asia'),('RO','Romania','Europe'),('RS','Serbia','Europe'),('RU','Russia','Europe'),('RW','Rwanda','Africa'),('SA','Saudi Arabia','Asia'),('SB','Solomon Islands','Oceania'),('SC','Seychelles','Africa'),('SD','Sudan','Africa'),('SE','Sweden','Europe'),('SG','Singapore','Asia'),('SI','Slovenia','Europe'),('SK','Slovakia','Europe'),('SL','Sierra Leone','Africa'),('SM','San Marino','Europe'),('SN','Senegal','Africa'),('SO','Somalia','Africa'),('SR','Suriname','South America'),('SS','South Sudan','Africa'),('ST','Sao Tome and Principe','Africa'),('SV','El Salvador','North America'),('SY','Syria','Asia'),('SZ','Eswatini','Africa'),('TD','Chad','Africa'),('TG','Togo','Africa'),('TH','Thailand','Asia'),('TJ','Tajikistan','Asia'),('TK','Tokelau','Oceania'),('TL','Timor-Leste','Asia'),('TM','Turkmenistan','Asia'),('TN','Tunisia','Africa'),('TO','Tonga','Oceania'),('TR','Turkey','Asia'),('TT','Trinidad and Tobago','North America'),('TV','Tuvalu','Oceania'),('TW','Taiwan','Asia'),('TZ','Tanzania','Africa'),('UA','Ukraine','Europe'),('UG','Uganda','Africa'),('US','United States','North America'),('UY','Uruguay','South America'),('UZ','Uzbekistan','Asia'),('VA','Vatican City','Europe'),('VC','Saint Vincent and the Grenadines','North America'),('VE','Venezuela','South America'),('VN','Vietnam','Asia'),('VU','Vanuatu','Oceania'),('WF','Wallis and Futuna','Oceania'),('WS','Samoa','Oceania'),('YE','Yemen','Asia'),('ZA','South Africa','Africa'),('ZM','Zambia','Africa'),('ZW','Zimbabwe','Africa');
/*!40000 ALTER TABLE `user_pool_country_codes` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `user_profile_map`
--

DROP TABLE IF EXISTS `user_profile_map`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_profile_map` (
  `MapID` int NOT NULL AUTO_INCREMENT,
  `user_id` varchar(64) DEFAULT NULL,
  `ProfileUID` varchar(20) NOT NULL,
  `CreatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`MapID`),
  KEY `UserID` (`user_id`),
  KEY `ProfileUID` (`ProfileUID`),
  CONSTRAINT `user_profile_map_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user_pool` (`user_id`),
  CONSTRAINT `user_profile_map_ibfk_2` FOREIGN KEY (`ProfileUID`) REFERENCES `user_profiles` (`ProfileUID`)
) ENGINE=InnoDB AUTO_INCREMENT=746 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user_profile_map`
--

LOCK TABLES `user_profile_map` WRITE;
/*!40000 ALTER TABLE `user_profile_map` DISABLE KEYS */;
/*!40000 ALTER TABLE `user_profile_map` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `user_profiles`
--

DROP TABLE IF EXISTS `user_profiles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_profiles` (
  `ProfileUID` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `CategoryID` int NOT NULL,
  `CategoryName` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `LevelCode` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `LevelDescription` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `ProfileCode` varchar(64) NOT NULL,
  `ProfileDescription` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  PRIMARY KEY (`ProfileUID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user_profiles`
--

LOCK TABLES `user_profiles` WRITE;
/*!40000 ALTER TABLE `user_profiles` DISABLE KEYS */;
/*!40000 ALTER TABLE `user_profiles` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `user_role`
--

DROP TABLE IF EXISTS `user_role`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_role` (
  `RoleID` varchar(20) NOT NULL,
  `RoleName` varchar(100) NOT NULL,
  `PermissionLevel` int NOT NULL,
  `Description` text,
  `CreatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `UpdatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`RoleID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user_role`
--

LOCK TABLES `user_role` WRITE;
/*!40000 ALTER TABLE `user_role` DISABLE KEYS */;
INSERT INTO `user_role` VALUES ('Admin','God / Site Admin',100,'Full system access. Approves bonus surveys and manages all users, projects, data, and settings.','2025-12-08 01:21:09','2025-12-08 01:21:09'),('BonusCreator','Bonus Survey Creator',40,'Can create bonus surveys and tasks. Requires Admin approval to publish.','2025-12-08 01:20:53','2025-12-08 01:20:53'),('Guest','Guest User',0,'Can access public UI pages only; cannot join trials or view restricted content. No NDA.','2025-12-08 01:19:54','2025-12-08 01:19:54'),('ITAdmin','IT / Database Admin',80,'Backend infrastructure admin with technical authority. Cannot run trials.','2025-12-08 01:21:05','2025-12-08 01:21:05'),('Legal','Legal Team',30,'Views participant records, NDA status, and compliance-related information.','2025-12-08 01:20:11','2025-12-17 06:32:54'),('Management','Management / Steering',60,'Views raw data, dashboards, and summaries; oversight role without edit permissions.','2025-12-08 01:20:57','2025-12-17 06:33:23'),('Participant','Participant',20,'Signed NDA. Can join trials, complete surveys, and manage own profile.','2025-12-08 01:20:01','2025-12-17 06:32:47'),('ProductTeam','Product Team Member',50,'Can request trials, view raw data, confirm NDAs, and review results.','2025-12-08 01:20:14','2025-12-17 06:33:22'),('UTLead','User Trial Lead',70,'Runs trials end-to-end including recruitment, survey setup, analysis, and reporting.','2025-12-08 01:21:03','2025-12-08 01:21:03');
/*!40000 ALTER TABLE `user_role` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `user_role_map`
--

DROP TABLE IF EXISTS `user_role_map`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_role_map` (
  `user_id` varchar(64) NOT NULL,
  `RoleID` varchar(20) NOT NULL,
  `PermissionLevel` int NOT NULL DEFAULT '0',
  `CreatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `UpdatedAt` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `uniq_user_role` (`user_id`),
  KEY `RoleID` (`RoleID`),
  KEY `idx_user_role_map_user` (`user_id`),
  CONSTRAINT `user_role_map_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user_pool` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user_role_map`
--

LOCK TABLES `user_role_map` WRITE;
/*!40000 ALTER TABLE `user_role_map` DISABLE KEYS */;
INSERT INTO `user_role_map` VALUES ('userid_09eb7cc3ef8f1','Legal',30,'2026-01-15 04:04:22','2026-01-15 05:16:18'),('userid_0b06625a1d1711f1b88b1e1ea10fb097','Participant',60,'2026-03-11 09:05:58','2026-03-11 09:05:58'),('userid_1056b715f03d1','BonusCreator',40,'2026-01-15 04:03:56','2026-01-15 05:40:43'),('userid_25a485371dde11f1b88b1e1ea10fb097','Participant',20,'2026-03-12 06:41:59','2026-03-12 06:41:59'),('userid_4b7dd36d1d0a11f1b88b1e1ea10fb097','Participant',20,'2026-03-11 08:45:03','2026-03-11 09:00:45'),('userid_4fec82c7eea61','Admin',100,'2026-01-11 04:42:28','2026-01-15 04:30:08'),('userid_5fa2eee31d0d11f1b88b1e1ea10fb097','Participant',50,'2026-03-11 09:05:54','2026-03-11 09:05:54'),('userid_730c643a1d0c11f1b88b1e1ea10fb097','Participant',40,'2026-03-11 09:05:51','2026-03-11 09:05:51'),('userid_7f3cc1331dec11f1b88b1e1ea10fb097','Participant',20,'2026-03-12 08:22:31','2026-03-12 08:22:31'),('userid_8c2a449ff5031','UTLead',70,'2026-01-19 07:08:19','2026-01-19 07:52:13'),('userid_8f10d38d1d2811f1b88b1e1ea10fb097','Participant',20,'2026-03-11 08:59:50','2026-03-11 08:59:50'),('userid_90f9324aedc91','Participant',20,'2026-01-10 02:42:57','2026-01-11 06:33:48'),('userid_d593d38eed2a1','UTLead',70,'2026-01-09 07:16:52','2026-01-16 07:06:03'),('userid_e12c2650f5b71','BonusCreator',40,'2026-01-20 04:33:27','2026-01-20 04:44:36'),('userid_eb5a17811ddf11f1b88b1e1ea10fb097','Participant',20,'2026-03-12 06:52:14','2026-03-12 06:52:14'),('userid_f8a5983e1d2711f1b88b1e1ea10fb097','Participant',30,'2026-03-11 09:05:45','2026-03-11 09:05:45'),('userid_fb8b4fd007e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b506807e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b508e07e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b50ac07e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b50c807e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b50e707e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b510307e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b512107e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b513f07e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b515907e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b517307e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b518f07e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b51aa07e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b51c507e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b51e107e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b51fc07e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b521707e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b523107e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b524c07e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b526a07e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b528507e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b52a007e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b52ba07e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b52d507e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b52f107e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b530d07e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b532707e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b534207e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b535c07e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b537607e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b539107e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b53ac07e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b53c807e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b53e207e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b53fd07e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b541807e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b543507e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b545107e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b546d07e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b548907e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b54a807e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b54c407e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b54df07e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19'),('userid_fb8b54fb07e01','Participant',20,'2026-02-12 07:08:19','2026-02-12 07:08:19');
/*!40000 ALTER TABLE `user_role_map` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping routines for database 'user_trial_system_v1'
--
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-03-31 18:22:53
