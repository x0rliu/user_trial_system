-- MySQL dump 10.13  Distrib 8.0.19, for Win64 (x86_64)
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
SET @MYSQLDUMP_TEMP_LOG_BIN = @@SESSION.SQL_LOG_BIN;
SET @@SESSION.SQL_LOG_BIN= 0;

--
-- GTID state at the beginning of the backup 
--

SET @@GLOBAL.GTID_PURGED=/*!80000 '+'*/ '';

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
) ENGINE=InnoDB AUTO_INCREMENT=27 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

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
) ENGINE=InnoDB AUTO_INCREMENT=400 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

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
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

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
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

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
) ENGINE=InnoDB AUTO_INCREMENT=27 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

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
) ENGINE=InnoDB AUTO_INCREMENT=42 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

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
  PRIMARY KEY (`ApplicantID`),
  UNIQUE KEY `uniq_round_user` (`RoundID`,`user_id`),
  KEY `RoundID` (`RoundID`),
  KEY `UserID` (`user_id`),
  CONSTRAINT `project_applicants_ibfk_1` FOREIGN KEY (`RoundID`) REFERENCES `project_rounds` (`RoundID`),
  CONSTRAINT `project_applicants_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `user_pool` (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

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
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

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
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

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
  PRIMARY KEY (`RoundID`),
  KEY `ProjectID` (`ProjectID`),
  KEY `UTLead_UserID` (`UTLead_UserID`),
  CONSTRAINT `project_rounds_ibfk_1` FOREIGN KEY (`ProjectID`) REFERENCES `project_projects` (`ProjectID`)
) ENGINE=InnoDB AUTO_INCREMENT=25 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

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
) ENGINE=InnoDB AUTO_INCREMENT=30 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

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
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

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
  `ProjectID` varchar(20) NOT NULL,
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
) ENGINE=InnoDB AUTO_INCREMENT=1190 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

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
) ENGINE=InnoDB AUTO_INCREMENT=31 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

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
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

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
-- Table structure for table `survey_upload_audit`
--

DROP TABLE IF EXISTS `survey_upload_audit`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `survey_upload_audit` (
  `UploadID` bigint unsigned NOT NULL AUTO_INCREMENT,
  `FileHash` char(64) NOT NULL,
  `OriginalFilename` varchar(255) DEFAULT NULL,
  `UploadedByUserID` varchar(20) DEFAULT NULL,
  `ProjectID` varchar(20) DEFAULT NULL,
  `RoundID` int DEFAULT NULL,
  `SurveyTypeID` varchar(20) DEFAULT NULL,
  `SurveyID` bigint unsigned DEFAULT NULL,
  `InsertedAnswerRows` int unsigned DEFAULT NULL,
  `UploadedAt` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`UploadID`),
  UNIQUE KEY `uniq_filehash` (`FileHash`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

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
) ENGINE=InnoDB AUTO_INCREMENT=1473 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

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
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

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
-- Dumping routines for database 'user_trial_system_v1'
--
SET @@SESSION.SQL_LOG_BIN = @MYSQLDUMP_TEMP_LOG_BIN;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-03-31 13:16:48
