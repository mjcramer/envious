import sbt.*

object Dependencies {
  import Modules.*

  lazy val base = Seq(zio, zioLogging, logback)
  lazy val config = Seq(zioConfig, zioConfigMagnolia, zioConfigTypesafe, zioConfigRefined)
  lazy val testing = Seq(zioTest, zioTestSbt)
}

object Versions {
  lazy val confluent = "7.9.1"
  lazy val logback = "1.5.18"
  lazy val scala = "3.3.1"
//  lazy val scalaLogging            = "3.9.5"
//  lazy val scalacheck              = "1.17.0"
//  lazy val scalamock               = "5.2.0"
//  lazy val scalatest               = "3.2.15"
//  lazy val scalatestPlusScalacheck = "3.2.2.0"
//  lazy val scalatestJunit          = "3.2.15.0"
//  lazy val slf4j                   = "2.0.7"
  lazy val zio = "2.1.18"
  lazy val zioConfig = "4.0.4"
  lazy val zioHttp = "3.2.0"
  lazy val zioJson = "0.7.43"
  lazy val zioKafka = "2.12.0"
  lazy val zioLogging = "2.5.0"
  lazy val zioSchema = "1.7.1"
}

object Modules {

  lazy val logback = "ch.qos.logback" % "logback-classic" % Versions.logback
//  lazy val scalaLogging    = "com.typesafe.scala-logging" %% "scala-logging"    % Versions.scalaLogging
//  lazy val scalatest       = "org.scalatest"              %% "scalatest"        % Versions.scalatest
//  lazy val scalacheck      = "org.scalacheck"             %% "scalacheck"       % Versions.scalacheck
//  lazy val scalamock       = "org.scalamock"              %% "scalamock"        % Versions.scalamock
//  lazy val scalatestJunit  = "org.scalatestplus"          %% "junit-4-13"       % Versions.scalatestJunit

  lazy val scalaProtobufRuntime =   "com.thesamet.scalapb" %% "scalapb-runtime" % scalapb.compiler.Version.scalapbVersion
  lazy val scalaReflect = "org.scala-lang" % "scala-reflect" % Versions.scala % "provided"

  lazy val zioLoggingSlf4j = "dev.zio" %% "zio-logging" % Versions.zioLogging
  lazy val zioLogging = "dev.zio" %% "zio-logging-slf4j" % Versions.zioLogging

  lazy val zio = "dev.zio" %% "zio" % Versions.zio
  lazy val zioConfig = "dev.zio" %% "zio-config" % Versions.zioConfig
  lazy val zioConfigMagnolia = "dev.zio" %% "zio-config-magnolia" % Versions.zioConfig
  lazy val zioConfigTypesafe = "dev.zio" %% "zio-config-typesafe" % Versions.zioConfig
  lazy val zioConfigRefined = "dev.zio" %% "zio-config-refined" % Versions.zioConfig
  lazy val zioHttp = "dev.zio" %% "zio-http" % Versions.zioHttp
  lazy val zioJson = "dev.zio" %% "zio-json" % Versions.zioJson
  lazy val zioKafka = "dev.zio" %% "zio-kafka" % Versions.zioKafka
  lazy val zioSchema = "dev.zio" %% "zio-schema" % Versions.zioSchema
  lazy val zioSchemaJson = "dev.zio" %% "zio-schema-json" % Versions.zioSchema
  lazy val zioSchemaTest = "dev.zio" %% "zio-schema-zio-test" % Versions.zioSchema
  lazy val zioSchemaDerivation = "dev.zio" %% "zio-schema-derivation" % Versions.zioSchema
  lazy val zioStreams = "dev.zio" %% "zio-streams" % Versions.zio
  lazy val zioTest = "dev.zio" %% "zio-test" % Versions.zio
  lazy val zioTestSbt = "dev.zio" %% "zio-test-sbt" % Versions.zio
  lazy val zioTestMagnolia = "dev.zio" %% "zio-test-magnolia" % Versions.zio
}
