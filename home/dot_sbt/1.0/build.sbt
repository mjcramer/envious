
dependencyUpdatesFilter -= moduleFilter(organization = "org.scala-lang")

import com.scalapenos.sbt.prompt.SbtPrompt.autoImport._

promptTheme := com.scalapenos.sbt.prompt.PromptThemes.ScalapenosTheme

//promptTheme := PromptTheme(
//  List(
//    text("sbt", fg(15).bg(0)),
//    gitBranch(clean = fg(235).bg(34), dirty = fg(235).bg(214)).padLeft("  ").padRight(" "),
//    currentProject(fg(235).bg(93)).pad(" "),
//    text(" ", NoStyle)
//  ),
//  (previous, next) ⇒ StyledText("", fg(previous.style.background).bg(next.style.background))
//)

