// Scala formatting standards
addSbtPlugin("org.scalameta" % "sbt-scalafmt" % "2.5.0")
// Versioning from git
addSbtPlugin("com.github.sbt" % "sbt-git" % "2.0.1")
// Packaging applications
addSbtPlugin("com.github.sbt" % "sbt-native-packager" % "1.9.16")

//addSbtPlugin("io.spray"       % "sbt-revolver"        % "0.10.0")
//addSbtPlugin("ch.epfl.scala"  % "sbt-scalafix"        % "0.10.4")
addSbtPlugin("dev.zio"        % "zio-sbt-ecosystem"   % "0.4.0-alpha.31")

addSbtPlugin("com.thesamet" % "sbt-protoc" % "1.0.7")

libraryDependencies += "com.thesamet.scalapb" %% "compilerplugin" % "0.11.17"