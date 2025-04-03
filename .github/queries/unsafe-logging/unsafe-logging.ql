/**
 * @name Unsafe logging of sensitive data
 * @description Detects logging of potentially sensitive data without sanitization.
 * @kind path-problem
 * @problem.severity warning
 * @id java/unsafe-logging
 * @tags security
 */

import java
import semmle.code.java.dataflow.TaintTracking
import semmle.code.java.dataflow.FlowSources
import DataFlow::PathGraph

/**
 * A taint-tracking configuration for detecting sensitive data flowing to logging methods.
 */
class SensitiveDataLoggingConfig extends TaintTracking::Configuration {
  SensitiveDataLoggingConfig() { this = "SensitiveDataLoggingConfig" }

  override predicate isSource(DataFlow::Node source) {
    exists(Parameter p |
      p = source.asParameter() and
      p.getType() instanceof TypeString and
      p.getName().toLowerCase().matches("%password%")
    )
  }

  override predicate isSink(DataFlow::Node sink) {
    exists(MethodAccess ma |
      ma.getMethod().hasName(["info", "debug", "warn", "error", "trace", "log"]) and
      (
        ma.getMethod().getDeclaringType().getASourceSupertype*().hasQualifiedName("org.slf4j", "Logger") or
        ma.getMethod().getDeclaringType().getASourceSupertype*().hasQualifiedName("org.apache.logging.log4j", "Logger") or
        ma.getMethod().getDeclaringType().getASourceSupertype*().hasQualifiedName("java.util.logging", "Logger")
      ) and
      sink.asExpr() = ma.getArgument(0)
    )
  }
}

from DataFlow::PathNode source, DataFlow::PathNode sink, SensitiveDataLoggingConfig config
where config.hasFlowPath(source, sink)
select sink.getNode(), source, sink, "Potentially unsafe logging of sensitive data from $@.", 
       source.getNode(), "sensitive parameter"
